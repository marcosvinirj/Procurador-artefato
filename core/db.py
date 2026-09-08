"""Acesso ao Supabase. Server-side apenas: usa a service key, que ignora RLS."""

from __future__ import annotations

import os
from datetime import date, timedelta
from functools import lru_cache
from typing import Any, Sequence

from supabase import Client, create_client

from core.scoring import Model, Snapshot

HISTORY_DAYS = 30
ACTIVE = "active"      # visivel publicamente, tracked normalmente
PENDING = "pending"    # descoberto, a espera de revisao humana
REJECTED = "rejected"  # revisto e recusado; guardado so para nao sugerir de novo
ARCHIVED = "archived"  # foi active, saturou por dias seguidos; reativa-se sozinho


@lru_cache(maxsize=1)
def client() -> Client:
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_SERVICE_KEY sao obrigatorias")
    return create_client(url, key)


def _num(value: Any) -> float | None:
    return None if value is None else float(value)


def _to_model(row: dict[str, Any], snapshots: Sequence[Snapshot]) -> Model:
    return Model(
        id=str(row["id"]),
        name=row["name"],
        category=row["category"],
        keyword=row["keyword"],
        synonyms=tuple(row.get("synonyms") or ()),
        snapshots=tuple(snapshots),
    )


def fetch_model_rows(category: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    """`status=None` devolve todos os estados — usado pelo cron, que tem de dar
    sinal aos candidatos pendentes tambem, para ja terem dados quando forem revistos."""
    query = client().table("models").select("*").order("name")
    if category:
        query = query.eq("category", category)  # parametrizado pelo cliente, nunca concatenado
    if status:
        query = query.eq("status", status)
    return query.execute().data or []


def load_models(category: str | None = None, days: int = HISTORY_DAYS, status: str | None = ACTIVE) -> list[Model]:
    """Modelos com o historico recente ja agrupado, prontos para score_models."""
    rows = fetch_model_rows(category, status)
    if not rows:
        return []
    since = (date.today() - timedelta(days=days)).isoformat()
    snaps = (
        client()
        .table("snapshots")
        .select("model_id, day, demand_raw, competition_raw, margin_est")
        .in_("model_id", [r["id"] for r in rows])
        .gte("day", since)
        .execute()
        .data
        or []
    )
    by_model: dict[str, list[Snapshot]] = {}
    for s in snaps:
        by_model.setdefault(str(s["model_id"]), []).append(
            Snapshot(
                day=date.fromisoformat(s["day"]),
                demand_raw=_num(s["demand_raw"]),
                competition_raw=_num(s["competition_raw"]),
                margin_est=_num(s["margin_est"]),
            )
        )
    return [_to_model(r, by_model.get(str(r["id"]), [])) for r in rows]


def save_snapshots(rows: Sequence[dict[str, Any]]) -> int:
    """Upsert idempotente: re-correr o cron no mesmo dia atualiza, nao duplica."""
    if not rows:
        return 0
    client().table("snapshots").upsert(list(rows), on_conflict="model_id,day").execute()
    return len(rows)


def insert_candidates(rows: Sequence[dict[str, Any]]) -> int:
    """Propostas da descoberta. `keyword` e unique: um termo ja conhecido (em
    qualquer estado) nunca duplica, mesmo que a descoberta o encontre outra vez."""
    if not rows:
        return 0
    client().table("models").upsert(list(rows), on_conflict="keyword", ignore_duplicates=True).execute()
    return len(rows)


def update_model(model_id: str, **fields: Any) -> None:
    """Update pontual — aprovar/rejeitar um candidato (um de cada vez, na revisao humana)."""
    if fields:
        client().table("models").update(fields).eq("id", model_id).execute()


def apply_lifecycle_changes(changes: Sequence[dict[str, Any]]) -> None:
    """Grava as mudancas de arquivamento/reativacao agrupadas por estado final.

    Um update() por modelo ja causou um timeout real (dezenas de pedidos em
    serie). Um upsert com so (id, status, streak) tambem nao serve: o PostgREST
    trata-o como INSERT e deixa name/category/keyword a null, violando os NOT
    NULL — outro 500 real. A saida e agrupar: a politica so produz um punhado
    de combinacoes distintas de (status, streak), nao uma por modelo, por isso
    um UPDATE por combinacao com `in_(ids)` fica em poucos pedidos e e um
    UPDATE mesmo, sem tentar inserir nada.
    """
    if not changes:
        return
    grouped: dict[tuple[str, int], list[str]] = {}
    for change in changes:
        grouped.setdefault((change["status"], change["low_score_streak"]), []).append(change["id"])

    for (status, streak), ids in grouped.items():
        client().table("models").update({"status": status, "low_score_streak": streak}).in_("id", ids).execute()
