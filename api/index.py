"""API do TrendPrint. Ponto unico Python: um so FastAPI, todas as rotas."""

from __future__ import annotations

import hmac
import logging
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StrictBool

from core import auth, db, discovery, lifecycle, sources
from core.scoring import Scored, score_models

log = logging.getLogger("trendprint")

# A recolha corre dentro do timeout da funcao (~10s no plano Hobby) e o cron so
# dispara 1x/dia, por isso uma unica execucao tem de cobrir o seed inteiro. Em
# serie nao cabia: os conectores sao I/O puro, logo vao em paralelo. Se ainda
# assim o orcamento esgotar, devolve next_offset e a fatia seguinte fica para
# uma chamada posterior. Voltou a 7.5s (de 6.0s) porque o arquivamento saiu
# daqui para /api/lifecycle: depois do loop so sobra um save_snapshots.
COLLECT_BUDGET_SECONDS = 7.5
COLLECT_WORKERS = 8
DISCOVER_BUDGET_SECONDS = 7.5
DISCOVER_PER_SEED = 3  # novos por semente, no maximo: a revisao humana tem de dar conta
FREE_PREVIEW = 2  # quantos do topo do ranking o plano gratis ve por inteiro
# Faixas que o gratis ve nos bloqueados. Largas de proposito, e alinhadas com os
# limiares de core/scoring (65 aberto, 45 saturado) para a cor nao mentir.
SCORE_BANDS = ((80, 100), (65, 79), (45, 64), (0, 44))

app = FastAPI(title="TrendPrint API", docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception) -> JSONResponse:
    """Nunca devolver stack traces: revelam estrutura interna e dependencias."""
    log.exception("erro nao tratado", exc_info=exc)
    return JSONResponse({"error": "internal_error"}, status_code=500)


def require_cron(authorization: Annotated[str | None, Header()] = None) -> None:
    """So o cron da Vercel (recolha, arquivamento, descoberta): nenhuma sessao,
    nem de admin, dispara estas rotas. compare_digest evita descobrir o segredo
    por timing byte a byte.
    """
    secret = os.environ.get("CRON_SECRET")
    if not secret or not authorization or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="unauthorized")


def require_admin(authorization: Annotated[str | None, Header()] = None) -> None:
    """Painel de admin e revisao de candidatos: o CRON_SECRET (script local) ou
    a sessao de uma conta com is_admin — que so se liga por SQL, nunca pela API."""
    secret = os.environ.get("CRON_SECRET")
    if secret and authorization and hmac.compare_digest(authorization.encode(), f"Bearer {secret}".encode()):
        return
    if not auth.viewer_from_authorization(authorization).is_admin:
        raise HTTPException(status_code=403, detail="admin_only")


def require_viewer(authorization: Annotated[str | None, Header()] = None) -> auth.Viewer:
    """O catalogo inteiro exige conta com email confirmado — ate a parte gratis."""
    viewer = auth.viewer_from_authorization(authorization)
    if not viewer.authenticated:
        raise HTTPException(status_code=401, detail="login_required")
    return viewer


def _free_ids(ranked: list[Scored]) -> set[str]:
    """O que o plano gratis ve: os primeiros do ranking GLOBAL dos ativos.
    Tem de ser calculado antes de qualquer filtro — se cada busca ou categoria
    tivesse o seu proprio "top", bastava variar a busca para ver tudo."""
    return {item.model.id for item in ranked[:FREE_PREVIEW]}


def _band(score: float) -> list[int]:
    # O score vive em 0–100; se um dia sair disso, cai na faixa mais baixa em vez de dar 500.
    return next(([low, high] for low, high in SCORE_BANDS if score >= low), list(SCORE_BANDS[-1]))


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
    viewer: Annotated[auth.Viewer, Depends(require_viewer)],
    category: Annotated[str | None, Query(max_length=40)] = None,
    q: Annotated[str | None, Query(max_length=64)] = None,
) -> dict[str, Any]:
    """Plano pago: tudo. Gratis: os FREE_PREVIEW do topo e, de cada um dos
    outros, so a categoria e a faixa larga do score, na ordem do ranking — o
    suficiente para despertar interesse. Nome, id e numeros nunca saem daqui
    para ser "borrados" no browser, onde qualquer um os leria."""
    models = db.load_models(status=db.ACTIVE)
    ranked = score_models(models)
    locked: list[dict[str, Any]] = []
    if not viewer.is_paid:
        free = _free_ids(ranked)
        locked = [
            {"category": item.model.category, "band": _band(item.score)}
            for item in ranked
            if item.model.id not in free
        ]
        ranked = [item for item in ranked if item.model.id in free]
    if category:
        ranked = [item for item in ranked if item.model.category == category]
    if q and (needle := q.strip().lower()):
        ranked = [item for item in ranked if _matches(item, needle)]
    return {
        "models": [_serialize(item) for item in ranked],
        "categories": sorted({m.category for m in models}),
        "locked": locked,
        "plan": "paid" if viewer.is_paid else "free",
    }


@app.get("/api/models/{model_id}")
def get_model(
    model_id: Annotated[UUID, Path()],
    viewer: Annotated[auth.Viewer, Depends(require_viewer)],
) -> dict[str, Any]:
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
    if not viewer.is_paid and target not in _free_ids(ranked):
        raise HTTPException(status_code=403, detail="paid_only")
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
    db.apply_lifecycle_changes(
        [{"id": c.model_id, "status": c.status, "low_score_streak": c.low_score_streak} for c in changes]
    )
    return len(changes)


@app.get("/api/collect", dependencies=[Depends(require_cron)])
def collect(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> dict[str, Any]:
    """Recolhe sinais para ativos, arquivados (para poderem reativar) e
    pendentes (um candidato chega a revisao com dados reais). Os ativos vao
    primeiro: se o orcamento nao chegar para todos, sao eles que o site mostra
    — por ordem alfabetica, os candidatos novos passavam a frente. Rejeitados
    ficam de fora: nao gastam a cota das APIs."""
    priority = {db.ACTIVE: 0, db.ARCHIVED: 1}
    rows = sorted(
        (r for r in db.fetch_model_rows() if r["status"] != db.REJECTED),
        key=lambda r: priority.get(r["status"], 2),
    )[offset : offset + limit]
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


@app.get("/api/lifecycle", dependencies=[Depends(require_cron)])
def lifecycle_route() -> dict[str, Any]:
    """Arquiva saturados e reativa recuperados. Rota propria, com cron proprio.

    Antes corria pendurada no fim de /api/collect, e so quando a recolha
    terminasse a lista toda — o que deixou de acontecer a medida que a lista
    cresceu (40 de 42 dentro do orcamento => arquivamento saltado, todos os
    dias). Separada, tem os seus ~10s inteiros e nao depende da recolha ter
    acabado: le sempre o snapshot mais recente de cada modelo, seja de hoje ou
    de ontem.
    """
    return {"lifecycle_changes": _apply_lifecycle()}


@app.get("/api/discover", dependencies=[Depends(require_cron)])
def discover(
    offset: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=25)] = 5,
) -> dict[str, Any]:
    """Propoe candidatos novos. Nunca fica publico sozinho — entra como
    'pending', so visivel em /api/candidates ate alguem aprovar.

    So aceita o que as pessoas pesquisam como impressao 3D ("3d printed ..."),
    nunca uma variacao de algo ja conhecido ("aquarius moon lamp" com "moon
    lamp" no ranking), e rejeita de vez os pendentes que falham nisto.
    Sem `offset` (o cron diario) as sementes rodam: cada dia um bloco
    diferente, em vez de explorar sempre os mesmos produtos."""
    rows = db.fetch_model_rows()
    pending = [r for r in rows if r["status"] == db.PENDING]
    duplicates = discovery.rejectable(pending, [r for r in rows if r["status"] != db.PENDING])
    db.apply_lifecycle_changes([{"id": i, "status": db.REJECTED, "low_score_streak": 0} for i in duplicates])

    seeds = discovery.seeds(rows)
    if offset is None:
        offset = date.today().toordinal() * limit % max(len(seeds), 1)
    batch = seeds[offset : offset + limit]
    known = discovery.known_terms(rows)
    deadline = time.monotonic() + DISCOVER_BUDGET_SECONDS
    candidates: list[dict[str, Any]] = []
    processed = 0

    client = sources.http_client()
    try:
        for term, category in batch:
            if time.monotonic() >= deadline:
                break
            added = 0
            for query in discovery.related_terms(client, term):
                if added == DISCOVER_PER_SEED:
                    break
                product = discovery.product_term(query)
                if product is None or discovery.is_variant(product, known):
                    continue
                if discovery.tokens(product) <= discovery.tokens(term):
                    continue  # e a propria semente dita de outra forma
                known.append(discovery.tokens(product))
                candidates.append(
                    {
                        "name": product.title(),
                        "category": category,
                        "keyword": product,
                        "status": db.PENDING,
                        "source": discovery.SOURCE,
                    }
                )
                added += 1
            processed += 1
    finally:
        client.close()

    db.insert_candidates(candidates)
    incomplete = processed < len(batch) or len(batch) == limit
    return {
        "duplicates_rejected": len(duplicates),
        "seeds_processed": processed,
        "candidates_proposed": len(candidates),
        "next_offset": offset + processed if incomplete else None,
    }


@app.get("/api/candidates", dependencies=[Depends(require_admin)])
def list_candidates() -> dict[str, Any]:
    """Candidatos pendentes com o sinal mais recente ja recolhido — numeros
    em bruto, nao o score normalizado (a pool de percentil e so dos ativos)."""
    rows = db.fetch_model_rows()
    pending = [r for r in rows if r["status"] == db.PENDING]
    # Variacoes e candidatos da busca antiga nem aparecem; o proximo /api/discover rejeita-os.
    hidden = set(discovery.rejectable(pending, [r for r in rows if r["status"] != db.PENDING]))
    models = {m.id: m for m in db.load_models(status=db.PENDING)}
    result = []
    for row in pending:
        if row["id"] in hidden:
            continue
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


@app.post("/api/candidates/{model_id}", dependencies=[Depends(require_admin)])
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


@app.get("/api/me")
def me(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    """Quem esta ligado e se pagou. So leitura: is_paid nunca vem do cliente."""
    viewer = auth.viewer_from_authorization(authorization)
    return {
        "authenticated": viewer.authenticated,
        "email": viewer.email,
        "is_paid": viewer.is_paid,
        "is_admin": viewer.is_admin,
    }


@app.get("/api/admin", dependencies=[Depends(require_admin)])
def admin_overview() -> dict[str, Any]:
    """Contas (com o plano) e quantos produtos ha em cada estado."""
    return {
        "users": [
            {
                "id": p["id"],
                "email": p.get("email"),
                "is_paid": p.get("is_paid") is True,
                "is_admin": p.get("is_admin") is True,
                "created_at": p.get("created_at"),
            }
            for p in db.list_profiles()
        ],
        "models": dict(Counter(row["status"] for row in db.fetch_model_rows())),
    }


class PlanBody(BaseModel):
    # So o plano. is_admin fica de fora de proposito: nem um admin promove outro pela API.
    is_paid: StrictBool


@app.post("/api/admin/users/{user_id}", dependencies=[Depends(require_admin)])
def set_user_plan(user_id: Annotated[UUID, Path()], body: Annotated[PlanBody, Body()]) -> dict[str, Any]:
    if not db.set_paid(str(user_id), body.is_paid):
        raise HTTPException(status_code=404, detail="not_found")
    return {"id": str(user_id), "is_paid": body.is_paid}


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    response = await call_next(request)
    # Todas as rotas dependem de quem pede (catalogo com login, gratis vs pago)
    # ou sao de administracao: nada pode ir para a cache partilhada da CDN —
    # seria servir a vista de um assinante pago a outra pessoa.
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    return response
