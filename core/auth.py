"""Quem esta a pedir, e se pagou.

Fail-closed por desenho: qualquer falha (token invalido ou expirado, rede,
base de dados) trata o pedido como anonimo e nao-pago. Nunca o contrario —
um erro nosso nunca pode desbloquear conteudo pago.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from core import db

TIMEOUT = httpx.Timeout(3.0, connect=2.0)


@dataclass(frozen=True)
class Viewer:
    user_id: str | None = None
    email: str | None = None
    is_paid: bool = False

    @property
    def authenticated(self) -> bool:
        return self.user_id is not None


ANONYMOUS = Viewer()


def viewer_from_authorization(authorization: str | None) -> Viewer:
    """Valida o token de sessao perguntando ao proprio Supabase (assinatura,
    expiracao e revogacao ficam do lado dele). Pedido HTTP sem estado, de
    proposito: nao usa o cliente partilhado de db.py, que se ficasse com a
    sessao de um utilizador passaria a obedecer ao RLS e partia a app toda."""
    if not authorization or not authorization.startswith("Bearer "):
        return ANONYMOUS
    token = authorization.removeprefix("Bearer ").strip()
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
    if not token or not url or not key:
        return ANONYMOUS
    try:
        response = httpx.get(
            f"{url}/auth/v1/user",
            headers={"apikey": key, "Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        user = response.json()
        user_id, email = str(user["id"]), user.get("email")
        confirmed = bool(user.get("email_confirmed_at"))
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        return ANONYMOUS
    # Email por confirmar (ou sessao anonima do Supabase) nao conta como conta:
    # o acesso exige um email valido, e so o link de confirmacao o prova.
    if not confirmed:
        return ANONYMOUS
    return Viewer(user_id=user_id, email=email, is_paid=db.is_paid(user_id))
