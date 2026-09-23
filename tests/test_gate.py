"""Catalogo com login: anonimo nao ve nada, gratis ve o topo, pago ve tudo."""

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api import index
from core import auth, db
from core.scoring import Model, Snapshot, score_models

FREE = auth.Viewer(user_id="u-free", email="f@x.y")
PRO = auth.Viewer(user_id="u-pro", email="p@x.y", plan="pro")
PAID = auth.Viewer(user_id="u-paid", email="p@x.y", plan="premium")


def listing(label: str, n: int) -> dict:
    return {
        "listing_id": n, "title": f"Anuncio {label} {n}", "url": f"https://www.etsy.com/listing/{n}/x",
        "price": 20.0 + n, "currency": "USD", "image": f"https://i.etsystatic.com/{label}-{n}.jpg",
    }


def model(label: str, category: str, demand: float, competition: float) -> Model:
    showcase = tuple(listing(label, n) for n in range(1, 5))
    snap = Snapshot(date(2026, 9, 5), demand, competition, 10.0, showcase)
    return Model(str(uuid.uuid5(uuid.NAMESPACE_URL, label)), f"Modelo {label}", category, f"kw {label}", (), (snap,))


MODELS = [
    model("a1", "toys", 90, 10),
    model("a2", "toys", 60, 50),
    model("a3", "toys", 10, 90),
    model("b1", "decor", 80, 20),
    model("b2", "decor", 20, 80),
]
# O gratis ve o melhor de CADA categoria, na ordem do ranking global.
_BEST: dict[str, str] = {}
for _s in score_models(MODELS):
    _BEST.setdefault(_s.model.category, _s.model.id)
TOP = [s.model.id for s in score_models(MODELS) if s.model.id in _BEST.values()]
LOCKED = [m for m in MODELS if m.id not in TOP]


@pytest.fixture
def client(monkeypatch):
    viewers = {"Bearer free": FREE, "Bearer pro": PRO, "Bearer paid": PAID}
    monkeypatch.setattr(auth, "viewer_from_authorization", lambda h: viewers.get(h, auth.ANONYMOUS))
    monkeypatch.setattr(db, "load_models", lambda *a, **k: MODELS)
    return TestClient(index.app)


def get(client, path, who=None):
    return client.get(path, headers={"Authorization": f"Bearer {who}"} if who else {})


@pytest.mark.parametrize("path", ["/api/models", f"/api/models/{MODELS[0].id}"])
@pytest.mark.parametrize("who", [None, "token-falso"])
def test_sem_login_nao_ve_nada(client, path, who):
    response = get(client, path, who)
    assert response.status_code == 401
    assert "Modelo" not in response.text


def test_gratis_ve_so_o_topo_e_contagens(client):
    response = get(client, "/api/models", "free")
    body = response.json()
    assert [m["id"] for m in body["models"]] == TOP
    assert body["plan"] == "free"
    ranked = score_models(MODELS)
    assert body["locked"] == [
        {"category": s.model.category, "band": index._band(s.score)} for s in ranked if s.model.id not in TOP
    ]
    assert body["categories"] == ["decor", "toys"]
    for hidden in LOCKED:  # nem nome, nem id, nem keyword do que esta bloqueado
        assert hidden.id not in response.text
        assert hidden.name not in response.text
        assert hidden.keyword not in response.text


@pytest.mark.parametrize("query", ["?q=modelo", "?q=kw", "?category=toys", "?category=decor", "?q=a2"])
def test_filtros_nao_revelam_bloqueados(client, query):
    """Variar a busca ou a categoria nunca traz um modelo fora do topo global."""
    body = get(client, f"/api/models{query}", "free").json()
    assert {m["id"] for m in body["models"]} <= set(TOP)


def test_pago_ve_tudo(client):
    body = get(client, "/api/models", "paid").json()
    assert len(body["models"]) == len(MODELS)
    assert body["locked"] == []
    assert body["plan"] == "premium"


def test_detalhe_bloqueado_no_gratis(client):
    hidden = LOCKED[0].id
    response = get(client, f"/api/models/{hidden}", "free")
    assert response.status_code == 403
    assert LOCKED[0].name not in response.text
    assert get(client, f"/api/models/{TOP[0]}", "free").status_code == 200
    assert get(client, f"/api/models/{hidden}", "paid").status_code == 200


def test_nada_vai_para_a_cache_partilhada(client):
    for who in (None, "free", "paid"):
        response = get(client, "/api/models", who)
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["vary"] == "Authorization"
    assert client.get("/api/me").headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize(
    "score,band",
    [(100, [80, 100]), (80, [80, 100]), (79.9, [65, 79]), (65, [65, 79]), (64.9, [45, 64]), (45, [45, 64]), (44.9, [0, 44]), (0, [0, 44]), (-3, [0, 44])],
)
def test_faixas_seguem_os_limiares_do_score(score, band):
    assert index._band(score) == band


def test_gratis_ve_um_de_cada_categoria(client):
    body = get(client, "/api/models", "free").json()
    categories = [m["category"] for m in body["models"]]
    assert sorted(categories) == sorted({m.category for m in MODELS})  # um de cada, sem repetir


def detail(client, who):
    return get(client, f"/api/models/{TOP[0]}", who).json()


def test_gratis_so_ve_a_foto_do_lider(client):
    body = detail(client, "free")
    label = next(m.keyword for m in MODELS if m.id == TOP[0]).split()[-1]
    assert body["showcase"] == [{"image": f"https://i.etsystatic.com/{label}-1.jpg"}]
    assert body["search_url"] is None
    assert "etsy.com/listing" not in get(client, "/api/models", "free").text  # nem link, nem titulo


def test_pro_ve_o_lider_inteiro_e_a_pesquisa(client):
    body = detail(client, "pro")
    assert len(body["showcase"]) == 1
    assert body["showcase"][0]["url"].startswith("https://www.etsy.com/listing/")
    assert body["search_url"].startswith("https://www.etsy.com/search?q=kw+")


def test_premium_ve_os_quatro_primeiros(client):
    body = detail(client, "paid")
    assert len(body["showcase"]) == 4
    assert body["search_url"]


def test_rotina_das_fotos_junta_so_o_que_falta(monkeypatch):
    from core import sources

    monkeypatch.setenv("CRON_SECRET", "segredo")
    rows = [
        {"model_id": "m1", "day": "2026-09-23", "showcase": [{"listing_id": 1}, {"listing_id": 2, "image": "https://i.etsystatic.com/ja.jpg"}]},
        {"model_id": "m2", "day": "2026-09-23", "showcase": [{"listing_id": 3}]},
    ]
    monkeypatch.setattr(db, "recent_showcases", lambda: rows)
    pedidos, gravados = [], []
    monkeypatch.setattr(sources, "etsy_images", lambda _c, ids: pedidos.append(list(ids)) or {1: "https://i.etsystatic.com/1.jpg"})
    monkeypatch.setattr(db, "save_showcases", lambda changed: gravados.extend(changed))

    body = TestClient(index.app).get("/api/showcase", headers={"Authorization": "Bearer segredo"}).json()

    assert pedidos == [[1, 3]]  # a 2 ja tinha foto
    assert body == {"listings_missing": 2, "images_found": 1, "rows_updated": 1}
    assert gravados[0]["showcase"][0]["image"] == "https://i.etsystatic.com/1.jpg"
