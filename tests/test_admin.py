"""Admin: so entra o CRON_SECRET ou uma conta com is_admin (que so se liga por SQL)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from api import index
from core import auth, db

ADMIN = auth.Viewer(user_id="u-admin", email="a@x.y", is_admin=True)
PAID = auth.Viewer(user_id="u-paid", email="p@x.y", plan="premium")
USER_ID = str(uuid.uuid4())
AS_ADMIN = {"Authorization": "Bearer admin"}


@pytest.fixture
def calls(monkeypatch):
    """Regista cada escrita: um teste de acesso negado tem de acabar sem nenhuma."""
    monkeypatch.setenv("CRON_SECRET", "segredo")
    viewers = {"Bearer admin": ADMIN, "Bearer paid": PAID}
    monkeypatch.setattr(auth, "viewer_from_authorization", lambda h: viewers.get(h, auth.ANONYMOUS))
    profile = {"id": USER_ID, "email": "c@x.y", "plan": "free", "is_admin": False, "created_at": "2026-09-16"}
    monkeypatch.setattr(db, "list_profiles", lambda: [profile])
    rows = [{"id": "m1", "status": "active"}, {"id": "m2", "status": "pending"}]
    monkeypatch.setattr(db, "fetch_model_rows", lambda *a, **k: rows)
    monkeypatch.setattr(db, "load_models", lambda *a, **k: [])
    log: list[tuple] = []
    monkeypatch.setattr(db, "set_plan", lambda uid, plan: log.append(("plan", uid, plan)) or uid == USER_ID)
    monkeypatch.setattr(db, "update_model", lambda mid, **fields: log.append(("model", mid, fields)))
    monkeypatch.setattr(db, "insert_candidates", lambda rows: log.append(("candidates", rows)))
    monkeypatch.setattr(db, "list_shops", lambda: [])
    monkeypatch.setattr(db, "add_shop", lambda *a: log.append(("shop", a)))
    monkeypatch.setattr(db, "remove_shop", lambda rid: log.append(("unshop", rid)))
    return log


@pytest.fixture
def client(calls):
    return TestClient(index.app)


ROUTES = [
    ("get", "/api/admin", None),
    ("get", "/api/candidates", None),
    ("post", f"/api/admin/users/{USER_ID}", {"plan": "pro"}),
    ("post", "/api/candidates/00000000-0000-0000-0000-000000000000", {"action": "reject"}),
    ("post", "/api/admin/discover", None),
    ("post", "/api/admin/watch", None),
    ("get", "/api/admin/shops", None),
    ("post", "/api/admin/shops", {"shop": "AnimeLab", "category": "geek"}),
    ("delete", f"/api/admin/shops/{USER_ID}", None),
]


@pytest.mark.parametrize("method,path,body", ROUTES)
@pytest.mark.parametrize("header", [None, "Bearer paid", "Bearer qualquer", "Bearer segredo-errado", "segredo"])
def test_so_admin_entra(client, calls, method, path, body, header):
    headers = {"Authorization": header} if header else {}
    response = client.request(method, path, json=body, headers=headers)
    assert response.status_code == 403
    assert calls == []


@pytest.mark.parametrize("header", ["Bearer admin", "Bearer segredo"])
def test_admin_ou_cron_veem_o_painel(client, header):
    response = client.get("/api/admin", headers={"Authorization": header})
    assert response.status_code == 200
    body = response.json()
    assert body["models"] == {"active": 1, "pending": 1}
    assert body["users"] == [
        {"id": USER_ID, "email": "c@x.y", "plan": "free", "is_admin": False, "created_at": "2026-09-16"}
    ]
    assert response.headers["cache-control"] == "private, no-store"


def test_admin_muda_o_plano(client, calls):
    # is_admin no corpo e ignorado: so o plano muda.
    body = {"plan": "premium", "is_admin": True}
    assert client.post(f"/api/admin/users/{USER_ID}", json=body, headers=AS_ADMIN).json() == {
        "id": USER_ID,
        "plan": "premium",
    }
    assert calls == [("plan", USER_ID, "premium")]
    missing = client.post(f"/api/admin/users/{uuid.uuid4()}", json={"plan": "free"}, headers=AS_ADMIN)
    assert missing.status_code == 404


@pytest.mark.parametrize("body", [{"plan": "gold"}, {"plan": 1}, {"is_paid": True}, {}, {"is_admin": True}])
def test_corpo_invalido_nao_muda_nada(client, calls, body):
    """So um booleano de verdade serve."""
    response = client.post(f"/api/admin/users/{USER_ID}", json=body, headers=AS_ADMIN)
    assert response.status_code == 422
    assert calls == []


def test_id_que_nao_e_uuid(client, calls):
    response = client.post("/api/admin/users/nao-e-uuid", json={"plan": "pro"}, headers=AS_ADMIN)
    assert response.status_code == 422
    assert calls == []
