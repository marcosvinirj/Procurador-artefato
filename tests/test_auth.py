"""Sessao e pago: fail-closed. Qualquer duvida => anonimo, nao pago."""

import httpx
import pytest

from core import auth, db


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service")


def respond(monkeypatch, status=200, body=None, exc=None):
    def fake_get(url, headers, timeout):
        if exc:
            raise exc
        return httpx.Response(status, json=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(auth.httpx, "get", fake_get)


def test_sem_token_e_anonimo():
    for header in (None, "", "Basic abc", "Bearer ", "Bearer    "):
        assert auth.viewer_from_authorization(header) == auth.ANONYMOUS


def test_sem_configuracao_e_anonimo(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL")
    assert auth.viewer_from_authorization("Bearer tok") == auth.ANONYMOUS


@pytest.mark.parametrize(
    "status,body,exc",
    [
        (401, {"msg": "invalid JWT"}, None),        # token falso ou expirado
        (200, {"sem": "id"}, None),                  # resposta estranha
        (200, None, None),                           # corpo vazio
        (200, None, httpx.ConnectTimeout("lento")),  # Supabase em baixo
    ],
)
def test_qualquer_falha_e_anonimo_mesmo_que_a_bd_dissesse_pago(monkeypatch, status, body, exc):
    respond(monkeypatch, status, body, exc)
    monkeypatch.setattr(db, "is_paid", lambda _uid: True)
    assert auth.viewer_from_authorization("Bearer tok") == auth.ANONYMOUS


def test_token_valido_le_o_pago_do_servidor(monkeypatch):
    respond(monkeypatch, 200, {"id": "u1", "email": "a@b.c", "email_confirmed_at": "2026-09-16T10:00:00Z"})
    monkeypatch.setattr(db, "is_paid", lambda uid: uid == "u1")
    viewer = auth.viewer_from_authorization("Bearer tok")
    assert viewer == auth.Viewer(user_id="u1", email="a@b.c", is_paid=True)
    assert viewer.authenticated


@pytest.mark.parametrize("confirmed_at", [None, ""])
def test_email_por_confirmar_e_anonimo(monkeypatch, confirmed_at):
    """Sessao valida mas email nunca confirmado (ou utilizador anonimo do Supabase)."""
    respond(monkeypatch, 200, {"id": "u1", "email": "a@b.c", "email_confirmed_at": confirmed_at})
    monkeypatch.setattr(db, "is_paid", lambda _uid: True)
    assert auth.viewer_from_authorization("Bearer tok") == auth.ANONYMOUS


class FakeTable:
    def __init__(self, rows=None, boom=False):
        self.rows, self.boom = rows, boom

    def table(self, _name):
        return self

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def limit(self, *_):
        return self

    def execute(self):
        if self.boom:
            raise RuntimeError("tabela profiles em falta")
        return type("R", (), {"data": self.rows})()


@pytest.mark.parametrize(
    "fake,expected",
    [
        (FakeTable(rows=[{"is_paid": True}]), True),
        (FakeTable(rows=[{"is_paid": False}]), False),
        (FakeTable(rows=[{"is_paid": "true"}]), False),  # so o booleano True conta
        (FakeTable(rows=[]), False),                      # sem perfil
        (FakeTable(boom=True), False),                    # erro => nao pago
    ],
)
def test_is_paid_fail_closed(monkeypatch, fake, expected):
    monkeypatch.setattr(db, "client", lambda: fake)
    assert db.is_paid("u1") is expected
