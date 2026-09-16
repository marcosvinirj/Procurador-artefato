"""Catalogo com login: anonimo nao ve nada, gratis ve o topo, pago ve tudo."""

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api import index
from core import auth, db
from core.scoring import Model, Snapshot, score_models

FREE = auth.Viewer(user_id="u-free", email="f@x.y")
PAID = auth.Viewer(user_id="u-paid", email="p@x.y", is_paid=True)


def model(label: str, category: str, demand: float, competition: float) -> Model:
    snap = Snapshot(date(2026, 9, 5), demand, competition, 10.0)
    return Model(str(uuid.uuid5(uuid.NAMESPACE_URL, label)), f"Modelo {label}", category, f"kw {label}", (), (snap,))


MODELS = [
    model("a1", "toys", 90, 10),
    model("a2", "toys", 60, 50),
    model("a3", "toys", 10, 90),
    model("b1", "decor", 80, 20),
    model("b2", "decor", 20, 80),
]
TOP = [s.model.id for s in score_models(MODELS)][: index.FREE_PREVIEW]
LOCKED = [m for m in MODELS if m.id not in TOP]


@pytest.fixture
def client(monkeypatch):
    viewers = {"Bearer free": FREE, "Bearer paid": PAID}
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
    assert body["plan"] == "paid"


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
