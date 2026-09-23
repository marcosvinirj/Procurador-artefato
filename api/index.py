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
from urllib.parse import quote_plus
from uuid import UUID

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core import auth, db, discovery, lifecycle, shops, sources
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
WATCH_BUDGET_SECONDS = 7.5
# Dois pedidos Etsy por loja e em serie; 4 lojas em paralelo ficam abaixo do
# limite de ~10 pedidos/s da API.
WATCH_WORKERS = 4
WATCH_PER_SHOP = 3  # candidatos novos por loja, no maximo
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
    """O que o plano gratis ve: o melhor de CADA categoria, no ranking GLOBAL
    dos ativos — uma montra de todos os nichos, nao so do topo. Tem de ser
    calculado antes de qualquer filtro: se cada busca ou categoria tivesse o
    seu proprio "top", bastava variar a busca para ver tudo."""
    best: dict[str, str] = {}
    for item in ranked:
        best.setdefault(item.model.category, item.model.id)
    return set(best.values())


def _band(score: float) -> list[int]:
    # O score vive em 0–100; se um dia sair disso, cai na faixa mais baixa em vez de dar 500.
    return next(([low, high] for low, high in SCORE_BANDS if score >= low), list(SCORE_BANDS[-1]))


def _showcase(item: Scored, plan: str) -> list[dict[str, Any]]:
    """Os anuncios da Etsy que cada plano ve: gratis so a foto do lider (sem
    link nem titulo), Pro o lider inteiro, Premium os primeiros SHOWCASE_SIZE.
    Decide-se aqui, no servidor: o que um plano nao ve nunca sai daqui."""
    listings = list(item.latest.showcase) if item.latest else []
    if plan == auth.FREE:
        return [{"image": x["image"]} for x in listings[:1] if x.get("image")]
    keep = sources.SHOWCASE_SIZE if plan == auth.PREMIUM else 1
    fields = ("title", "url", "price", "currency", "image")
    return [{k: x.get(k) for k in fields} for x in listings[:keep]]


def _serialize(item: Scored, plan: str) -> dict[str, Any]:
    model, snap = item.model, item.latest
    return {
        "showcase": _showcase(item, plan),
        # A pesquisa exata que gerou os numeros: e ela que o utilizador ve na Etsy.
        "search_url": f"https://www.etsy.com/search?q={quote_plus(model.keyword)}" if plan != auth.FREE else None,
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
    """Pro e Premium: tudo. Gratis: o melhor de cada categoria e, de cada um
    dos outros, so a categoria e a faixa larga do score, na ordem do ranking — o
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
        "models": [_serialize(item, viewer.plan) for item in ranked],
        "categories": sorted({m.category for m in models}),
        "locked": locked,
        "plan": viewer.plan,
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
        **_serialize(item, viewer.plan),
        "plan": viewer.plan,
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
                    "showcase": list(signal.showcase) or None,
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


@app.get("/api/showcase", dependencies=[Depends(require_cron)])
def showcase_images() -> dict[str, Any]:
    """Junta a foto a cada anuncio da vitrine. A busca da Etsy nao traz fotos;
    o endpoint em lote traz, ate 100 anuncios por pedido — 60 produtos x 4
    anuncios sao 3 pedidos por dia. So pede o que ainda nao tem foto."""
    rows = db.recent_showcases()
    missing = sorted({x["listing_id"] for r in rows for x in r["showcase"] if not x.get("image")})
    images: dict[int, str] = {}
    client = sources.http_client()
    try:
        for start in range(0, len(missing), 100):
            images.update(sources.etsy_images(client, missing[start : start + 100]))
    finally:
        client.close()
    changed = []
    for row in rows:
        updated = [{**x, "image": images[x["listing_id"]]} if x["listing_id"] in images else x for x in row["showcase"]]
        if updated != row["showcase"]:
            changed.append({**row, "showcase": updated})
    db.save_showcases(changed)
    return {"listings_missing": len(missing), "images_found": len(images), "rows_updated": len(changed)}


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


def _discover(offset: int | None, limit: int) -> dict[str, Any]:
    """Procura produtos novos e limpa os pendentes que nao servem. Usada pelo
    cron diario e pelo botao do painel de admin.

    So aceita o que as pessoas pesquisam como impressao 3D ("3d printed ..."),
    nunca uma variacao de algo ja conhecido ("aquarius moon lamp" com "moon
    lamp" no ranking), e rejeita de vez os pendentes que falham nisto. Sem
    `offset` (o cron diario) as sementes rodam: cada dia um bloco diferente,
    em vez de explorar sempre os mesmos produtos."""
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
            for query in discovery.suggested_terms(client, term):
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


@app.get("/api/discover", dependencies=[Depends(require_cron)])
def discover(
    offset: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=25)] = 5,
) -> dict[str, Any]:
    """Cron diario. Nunca publica sozinho: o candidato entra como 'pending' e so
    fica visivel em /api/models depois de aprovado em /api/candidates."""
    return _discover(offset, limit)


@app.post("/api/admin/discover", dependencies=[Depends(require_admin)])
def discover_now(limit: Annotated[int, Query(ge=1, le=25)] = 5) -> dict[str, Any]:
    """O mesmo, a pedido do admin, sem esperar pelo cron."""
    return _discover(None, limit)


def _watch() -> dict[str, Any]:
    """Das lojas vigiadas, os produtos lancados ha pouco que ja vendem (ver
    core/shops.py). Entram na mesma fila da descoberta, como 'pending', com a
    categoria que o admin deu a loja e a loja na `source` — quem revê sabe de
    onde veio. Nunca propoe uma variacao de algo ja conhecido."""
    watched = db.list_shops()
    known = discovery.known_terms(db.fetch_model_rows())
    now = int(time.time())
    deadline = time.monotonic() + WATCH_BUDGET_SECONDS
    candidates: list[dict[str, Any]] = []
    checked = 0

    client = sources.http_client()
    pool = ThreadPoolExecutor(max_workers=WATCH_WORKERS)
    try:
        futures = {pool.submit(shops.rising_listings, client, s["shop_id"], now): s for s in watched}
        for future, shop in futures.items():
            if time.monotonic() >= deadline:
                break
            try:
                rising = future.result(timeout=deadline - time.monotonic())
            except Exception:  # orcamento esgotado: a loja fica para amanha
                continue
            checked += 1
            added = 0
            for _reviews, listing in rising:
                if added == WATCH_PER_SHOP:
                    break
                term = shops.title_term(str(listing.get("title") or ""))
                if term is None or discovery.is_variant(term, known):
                    continue
                known.append(discovery.tokens(term))
                candidates.append(
                    {
                        "name": term.title(),
                        "category": shop["category"],
                        "keyword": term,
                        "status": db.PENDING,
                        "source": f"{shops.SOURCE}:{shop['shop_name']}",
                    }
                )
                added += 1
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
        client.close()

    db.insert_candidates(candidates)
    return {"shops_checked": checked, "candidates_proposed": len(candidates)}


@app.get("/api/watch", dependencies=[Depends(require_cron)])
def watch() -> dict[str, Any]:
    """Cron diario do vigia de lojas. Nunca publica sozinho (invariante 8)."""
    return _watch()


@app.post("/api/admin/watch", dependencies=[Depends(require_admin)])
def watch_now() -> dict[str, Any]:
    """O mesmo, a pedido do admin, sem esperar pelo cron."""
    return _watch()


def _categories() -> list[str]:
    return sorted({row["category"] for row in db.fetch_model_rows()})


@app.get("/api/admin/shops", dependencies=[Depends(require_admin)])
def list_watched_shops() -> dict[str, Any]:
    return {
        "shops": [
            {"id": s["id"], "shop_name": s["shop_name"], "category": s["category"]} for s in db.list_shops()
        ],
        "categories": _categories(),
    }


class ShopBody(BaseModel):
    shop: str = Field(min_length=2, max_length=200)  # nome ou link da loja
    category: str = Field(min_length=1, max_length=40)


@app.post("/api/admin/shops", dependencies=[Depends(require_admin)])
def add_watched_shop(body: Annotated[ShopBody, Body()]) -> dict[str, Any]:
    """Resolve o nome na Etsy antes de gravar: so entra uma loja que existe, e
    so numa categoria que ja existe (e para la que vao os candidatos dela)."""
    name = shops.shop_name_from(body.shop)
    if name is None:
        raise HTTPException(status_code=422, detail="invalid_shop")
    if body.category not in _categories():
        raise HTTPException(status_code=422, detail="invalid_category")
    client = sources.http_client()
    try:
        found = shops.find_shop(client, name)
    finally:
        client.close()
    if found is None:
        raise HTTPException(status_code=404, detail="shop_not_found")
    row = db.add_shop(found["shop_id"], found["shop_name"], body.category)
    return {"shop": {"id": row.get("id"), "shop_name": found["shop_name"], "category": body.category}}


@app.delete("/api/admin/shops/{row_id}", dependencies=[Depends(require_admin)])
def remove_watched_shop(row_id: Annotated[UUID, Path()]) -> dict[str, Any]:
    if not db.remove_shop(str(row_id)):
        raise HTTPException(status_code=404, detail="not_found")
    return {"id": str(row_id)}


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
        "plan": viewer.plan,
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
                "plan": p.get("plan") if p.get("plan") in auth.PLANS else ("pro" if p.get("is_paid") else "free"),
                "is_admin": p.get("is_admin") is True,
                "created_at": p.get("created_at"),
            }
            for p in db.list_profiles()
        ],
        "models": dict(Counter(row["status"] for row in db.fetch_model_rows())),
    }


class PlanBody(BaseModel):
    # So o plano. is_admin fica de fora de proposito: nem um admin promove outro pela API.
    plan: Literal["free", "pro", "premium"]


@app.post("/api/admin/users/{user_id}", dependencies=[Depends(require_admin)])
def set_user_plan(user_id: Annotated[UUID, Path()], body: Annotated[PlanBody, Body()]) -> dict[str, Any]:
    if not db.set_plan(str(user_id), body.plan):
        raise HTTPException(status_code=404, detail="not_found")
    return {"id": str(user_id), "plan": body.plan}


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    response = await call_next(request)
    # Todas as rotas dependem de quem pede (catalogo com login, gratis vs pago)
    # ou sao de administracao: nada pode ir para a cache partilhada da CDN —
    # seria servir a vista de um assinante pago a outra pessoa.
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    return response
