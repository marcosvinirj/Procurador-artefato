"""API do TrendPrint. Ponto unico Python: um so FastAPI, tres rotas."""

from __future__ import annotations

import hmac
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse

from core import db, sources
from core.scoring import Model, Scored, score_models

log = logging.getLogger("trendprint")

# A recolha corre dentro do timeout da funcao (~10s no plano Hobby) e o cron so
# dispara 1x/dia, por isso uma unica execucao tem de cobrir o seed inteiro. Em
# serie nao cabia: os conectores sao I/O puro, logo vao em paralelo. Se ainda
# assim o orcamento esgotar, devolve next_offset e a fatia seguinte fica para
# uma chamada posterior.
COLLECT_BUDGET_SECONDS = 7.5
COLLECT_WORKERS = 8
LIST_CACHE = "public, max-age=0, s-maxage=300, stale-while-revalidate=600"

app = FastAPI(title="TrendPrint API", docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception) -> JSONResponse:
    """Nunca devolver stack traces: revelam estrutura interna e dependencias."""
    log.exception("erro nao tratado", exc_info=exc)
    return JSONResponse({"error": "internal_error"}, status_code=500)


def require_cron(authorization: Annotated[str | None, Header()] = None) -> None:
    """Autoriza so o cron da Vercel, que envia `Authorization: Bearer $CRON_SECRET`.

    compare_digest evita que o segredo seja descoberto por timing byte a byte.
    """
    secret = os.environ.get("CRON_SECRET")
    if not secret or not authorization or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="unauthorized")


def _serialize(item: Scored) -> dict[str, Any]:
    model, snap = item.model, item.latest
    return {
        "id": model.id,
        "name": model.name,
        "category": model.category,
        "keyword": model.keyword,
        "synonyms": list(model.synonyms),
        "score": item.score,
        "demand_norm": item.demand_norm,
        "competition_norm": item.competition_norm,
        "components": item.components,
        "contributions": item.contributions,
        "updated_at": snap.day.isoformat() if snap else None,
    }


def _matches(item: Scored, needle: str) -> bool:
    haystack = " ".join((item.model.name, item.model.keyword, *item.model.synonyms)).lower()
    return needle in haystack


@app.get("/api/models")
def list_models(
    category: Annotated[str | None, Query(max_length=40)] = None,
    q: Annotated[str | None, Query(max_length=64)] = None,
) -> dict[str, Any]:
    models = db.load_models(category)
    ranked = score_models(models)
    if q and (needle := q.strip().lower()):
        ranked = [item for item in ranked if _matches(item, needle)]
    return {
        "models": [_serialize(item) for item in ranked],
        "categories": sorted({m.category for m in models}),
    }


@app.get("/api/models/{model_id}")
def get_model(model_id: Annotated[UUID, Path()]) -> dict[str, Any]:
    """Detalhe: o score vem do ranking completo, senao o percentil perdia a
    referencia da categoria e o gap deixava de ser comparavel."""
    target = str(model_id)
    ranked = score_models(db.load_models())
    item = next((s for s in ranked if s.model.id == target), None)
    if item is None:
        raise HTTPException(status_code=404, detail="not_found")
    return {
        **_serialize(item),
        "history": [
            {
                "day": s.day.isoformat(),
                "demand_raw": s.demand_raw,
                "competition_raw": s.competition_raw,
                "margin_est": s.margin_est,
            }
            for s in sorted(item.model.snapshots, key=lambda s: s.day)
        ],
    }


@app.get("/api/collect", dependencies=[Depends(require_cron)])
def collect(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> dict[str, Any]:
    rows = db.fetch_model_rows()[offset : offset + limit]
    today = date.today().isoformat()
    deadline = time.monotonic() + COLLECT_BUDGET_SECONDS
    snapshots: list[dict[str, Any]] = []
    processed = 0

    client = sources.http_client()
    pool = ThreadPoolExecutor(max_workers=COLLECT_WORKERS)
    try:
        futures = {pool.submit(sources.collect, row, client): row for row in rows}
        for future, row in futures.items():
            if time.monotonic() >= deadline:
                break
            try:
                signal = future.result(timeout=deadline - time.monotonic())
            except Exception:  # orcamento esgotado ou conector em baixo: fica para a proxima
                continue
            processed += 1
            if signal == sources.Signal():
                continue  # nenhum conector respondeu: nao gravar uma linha vazia
            snapshots.append(
                {
                    "model_id": row["id"],
                    "day": today,
                    "demand_raw": signal.demand_raw,
                    "competition_raw": signal.competition_raw,
                    "margin_est": signal.margin_est,
                }
            )
    finally:
        # wait=False: o que sobrar do orcamento nao pode segurar a resposta.
        pool.shutdown(wait=False, cancel_futures=True)
        client.close()

    saved = db.save_snapshots(snapshots)
    # Sobra trabalho se o orcamento cortou a fatia a meio, ou se a fatia veio cheia.
    incomplete = processed < len(rows) or len(rows) == limit
    return {
        "day": today,
        "processed": processed,
        "saved": saved,
        "next_offset": offset + processed if incomplete else None,
    }


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    response = await call_next(request)
    cacheable = response.status_code < 400 and not request.url.path.startswith("/api/collect")
    response.headers["Cache-Control"] = LIST_CACHE if cacheable else "no-store"
    return response
