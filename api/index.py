"""API do TrendPrint. Ponto unico Python: um so FastAPI, todas as rotas."""

from __future__ import annotations

import hmac
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core import db, discovery, lifecycle, sources
from core.scoring import Scored, score_models

log = logging.getLogger("trendprint")

# A recolha corre dentro do timeout da funcao (~10s no plano Hobby) e o cron so
# dispara 1x/dia, por isso uma unica execucao tem de cobrir o seed inteiro. Em
# serie nao cabia: os conectores sao I/O puro, logo vao em paralelo. Se ainda
# assim o orcamento esgotar, devolve next_offset e a fatia seguinte fica para
# uma chamada posterior.
COLLECT_BUDGET_SECONDS = 7.5
COLLECT_WORKERS = 8
DISCOVER_BUDGET_SECONDS = 7.5
LIST_CACHE = "public, max-age=0, s-maxage=300, stale-while-revalidate=600"

app = FastAPI(title="TrendPrint API", docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception) -> JSONResponse:
    """Nunca devolver stack traces: revelam estrutura interna e dependencias."""
    log.exception("erro nao tratado", exc_info=exc)
    return JSONResponse({"error": "internal_error"}, status_code=500)


def require_cron(authorization: Annotated[str | None, Header()] = None) -> None:
    """Autoriza o cron da Vercel e as rotas de administracao (descoberta,
    revisao de candidatos) com o mesmo segredo — nao ha sistema de contas
    nesta app (fora do escopo do MVP), por isso o CRON_SECRET faz de credencial
    unica. compare_digest evita descobri-lo por timing byte a byte.
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
    models = db.load_models(category, status=db.ACTIVE)
    ranked = score_models(models)
    if q and (needle := q.strip().lower()):
        ranked = [item for item in ranked if _matches(item, needle)]
    return {
        "models": [_serialize(item) for item in ranked],
        "categories": sorted({m.category for m in models}),
    }


@app.get("/api/models/{model_id}")
def get_model(model_id: Annotated[UUID, Path()]) -> dict[str, Any]:
    """Detalhe: o score vem do ranking dos ativos, senao o percentil perdia a
    referencia da categoria e o gap deixava de ser comparavel.

    Um modelo arquivado ainda abre (o link pode estar guardado nalgum lado; o
    historico continua real) — recalculado no contexto dos ativos da mesma
    categoria, sem entrar na pool deles. Pendente ou rejeitado nunca aparecem
    aqui: ainda nao foram aprovados para serem publicos.
    """
    target = str(model_id)
    active = db.load_models(status=db.ACTIVE)
    ranked = score_models(active)
    item = next((s for s in ranked if s.model.id == target), None)

    if item is None:
        rows = db.fetch_model_rows()
        row = next((r for r in rows if r["id"] == target), None)
        if row is None or row["status"] != db.ARCHIVED:
            raise HTTPException(status_code=404, detail="not_found")
        archived_model = next((m for m in db.load_models(status=db.ARCHIVED) if m.id == target), None)
        if archived_model is None:
            raise HTTPException(status_code=404, detail="not_found")
        peers = [m for m in active if m.category == archived_model.category]
        ranked = score_models([*peers, archived_model])
        item = next(s for s in ranked if s.model.id == target)

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


def _apply_lifecycle() -> int:
    """Arquiva quem satura por dias seguidos, reativa quem recupera. Ver
    core/lifecycle.py para a regra; aqui e so a orquestracao com a base de dados."""
    rows = {r["id"]: r for r in db.fetch_model_rows()}
    active_ids = [rid for rid, r in rows.items() if r["status"] == db.ACTIVE]
    archived_ids = [rid for rid, r in rows.items() if r["status"] == db.ARCHIVED]
    if not active_ids and not archived_ids:
        return 0

    active_models = db.load_models(status=db.ACTIVE)
    scores = {s.model.id: s.score for s in score_models(active_models)}

    if archived_ids:
        archived_by_id = {m.id: m for m in db.load_models(status=db.ARCHIVED)}
        for archived_id in archived_ids:
            model = archived_by_id.get(archived_id)
            if model is None:
                continue
            # avaliado no contexto dos ativos da sua categoria, sem entrar na
            # pool deles — a mesma logica de get_model para um item arquivado.
            peers = [m for m in active_models if m.category == model.category]
            scored_with_peer = score_models([*peers, model])
            scores[archived_id] = next(s.score for s in scored_with_peer if s.model.id == archived_id)

    relevant_ids = (*active_ids, *archived_ids)
    statuses = {rid: rows[rid]["status"] for rid in relevant_ids}
    streaks = {rid: rows[rid].get("low_score_streak", 0) for rid in relevant_ids}

    changes = lifecycle.decide(scores, statuses, streaks)
    for change in changes:
        db.update_model(change.model_id, status=change.status, low_score_streak=change.low_score_streak)
    return len(changes)


@app.get("/api/collect", dependencies=[Depends(require_cron)])
def collect(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> dict[str, Any]:
    """Recolhe sinais para TODOS os estados (inclui pending: um candidato ja
    chega a revisao com dados reais, nao as escuras)."""
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
    next_offset = offset + processed if incomplete else None

    # So arquiva/reativa quando a passagem de hoje estiver completa — julgar a
    # meio de uma fatia misturaria snapshots de hoje com os de ontem.
    lifecycle_changes = _apply_lifecycle() if next_offset is None else 0

    return {
        "day": today,
        "processed": processed,
        "saved": saved,
        "next_offset": next_offset,
        "lifecycle_changes": lifecycle_changes,
    }


@app.get("/api/discover", dependencies=[Depends(require_cron)])
def discover(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=25)] = 5,
) -> dict[str, Any]:
    """Propoe candidatos novos a partir dos modelos ativos (sementes para o
    Google Trends). Nunca fica publico sozinho — entra como 'pending', so
    visivel em /api/candidates ate alguem aprovar."""
    seeds = db.fetch_model_rows(status=db.ACTIVE)[offset : offset + limit]
    deadline = time.monotonic() + DISCOVER_BUDGET_SECONDS
    candidates: list[dict[str, Any]] = []
    processed = 0

    client = sources.http_client()
    try:
        for seed in seeds:
            if time.monotonic() >= deadline:
                break
            for query in discovery.related_terms(client, seed["keyword"]):
                candidates.append(
                    {
                        "name": query.title(),
                        "category": seed["category"],
                        "keyword": query.lower(),
                        "status": db.PENDING,
                        "source": "google_trends_related",
                    }
                )
            processed += 1
    finally:
        client.close()

    db.insert_candidates(candidates)
    incomplete = processed < len(seeds) or len(seeds) == limit
    return {
        "seeds_processed": processed,
        "candidates_proposed": len(candidates),
        "next_offset": offset + processed if incomplete else None,
    }


@app.get("/api/candidates", dependencies=[Depends(require_cron)])
def list_candidates() -> dict[str, Any]:
    """Candidatos pendentes com o sinal mais recente ja recolhido — numeros
    em bruto, nao o score normalizado (a pool de percentil e so dos ativos)."""
    rows = db.fetch_model_rows(status=db.PENDING)
    models = {m.id: m for m in db.load_models(status=db.PENDING)}
    result = []
    for row in rows:
        model = models.get(row["id"])
        latest = sorted(model.snapshots, key=lambda s: s.day)[-1] if model and model.snapshots else None
        result.append(
            {
                "id": row["id"],
                "name": row["name"],
                "category": row["category"],
                "keyword": row["keyword"],
                "source": row.get("source"),
                "created_at": row.get("created_at"),
                "demand_raw": latest.demand_raw if latest else None,
                "competition_raw": latest.competition_raw if latest else None,
                "margin_est": latest.margin_est if latest else None,
            }
        )
    return {"candidates": result}


class ReviewBody(BaseModel):
    action: Literal["approve", "reject"]
    name: str | None = None
    category: str | None = None


@app.post("/api/candidates/{model_id}", dependencies=[Depends(require_cron)])
def review_candidate(model_id: Annotated[UUID, Path()], body: Annotated[ReviewBody, Body()]) -> dict[str, Any]:
    target = str(model_id)
    row = next((r for r in db.fetch_model_rows(status=db.PENDING) if r["id"] == target), None)
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")

    if body.action == "reject":
        db.update_model(target, status=db.REJECTED)
        return {"id": target, "status": db.REJECTED}

    fields: dict[str, Any] = {"status": db.ACTIVE}
    if body.name:
        fields["name"] = body.name
    if body.category:
        fields["category"] = body.category
    db.update_model(target, **fields)
    return {"id": target, "status": db.ACTIVE}


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    response = await call_next(request)
    admin_route = request.url.path.startswith(("/api/collect", "/api/discover", "/api/candidates"))
    cacheable = response.status_code < 400 and not admin_route
    response.headers["Cache-Control"] = LIST_CACHE if cacheable else "no-store"
    return response
