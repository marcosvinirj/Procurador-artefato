"""Descoberta sem duplicados: variacoes de um produto conhecido nunca entram."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from api import index
from core import db, discovery, sources
from core.discovery import is_variant, known_terms, redundant, tokens

CRON = {"Authorization": "Bearer segredo"}


def row(keyword, status="active", category="decoracao", synonyms=(), rid=None):
    return {"id": rid or keyword, "name": keyword.title(), "keyword": keyword, "category": category,
            "status": status, "synonyms": list(synonyms)}


KNOWN = known_terms([row("moon lamp", synonyms=["luna lamp"]), row("earbud case"), row("phone case")])


def test_tokens_ignora_plural_e_ruido():
    assert tokens("3D Printed Moon Lamps STL") == {"moon", "lamp"}
    assert tokens("storage boxes") == tokens("storage box")
    assert tokens("glass vase") == {"glass", "vase"}


@pytest.mark.parametrize(
    "term",
    [
        "1970s aquarius moon lamp",  # os que apareceram no painel
        "aquarius moon lamp",
        "ecolor moon lamp",
        "beats earbud case",
        "bose earbud case",
        "earbud case holder",
        "bedazzled phone case",
        "moon lamps stl",  # plural + ruido
        "luna lamp free",  # sinonimo tambem conta
        "lamp",  # contido num conhecido: generico demais
        "3d printed",  # so ruido: nao e produto nenhum
    ],
)
def test_variacoes_sao_barradas(term):
    assert is_variant(term, KNOWN)


@pytest.mark.parametrize("term", ["dragon egg", "blunt cases", "3d printed chess set", "lamp shade"])
def test_produtos_diferentes_passam(term):
    assert not is_variant(term, KNOWN)


def test_pendentes_redundantes_entre_si_fica_o_mais_generico():
    pending = [
        row("aquarius moon lamp", "pending"),
        row("3d printed dragon egg", "pending"),
        row("dragon egg", "pending"),
        row("chess set", "pending"),
    ]
    assert sorted(redundant(pending, [row("moon lamp")])) == ["3d printed dragon egg", "aquarius moon lamp"]


def test_nome_sem_o_prefixo():
    assert discovery.display_name("3d printed dragon egg") == "Dragon Egg"
    assert discovery.display_name("3d printed") == "3D Printed"


class FakeClient:
    def close(self):
        pass


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "segredo")
    rows = [
        row("moon lamp"),
        row("aquarius moon lamp", "pending", rid="p1"),  # variacao antiga: rejeitar
        row("chess set", "pending", rid="p2"),  # candidato valido: fica
        row("cat toy", "rejected", category="brinquedos"),  # rejeitado continua conhecido
    ]
    written = {"inserted": [], "rejected": []}
    monkeypatch.setattr(db, "fetch_model_rows", lambda *a, **k: rows)
    monkeypatch.setattr(db, "load_models", lambda *a, **k: [])
    monkeypatch.setattr(db, "insert_candidates", lambda c: written["inserted"].extend(c))
    monkeypatch.setattr(
        db, "apply_lifecycle_changes", lambda ch: written["rejected"].extend(c["id"] for c in ch if c["status"] == "rejected")
    )
    monkeypatch.setattr(sources, "http_client", FakeClient)
    return TestClient(index.app), written


def test_descoberta_nao_propoe_variacoes_e_limpa_as_antigas(api, monkeypatch):
    client, written = api
    related = {
        "3d printed toys": ["3d printed toys", "cat toys", "3d printed dragon egg", "dragon eggs",
                            "fidget spinner", "chess set", "marble run", "rubber band gun", "dice box"],
        "moon lamp": ["moon lamp stl", "aquarius moon lamp", "night light"],
    }
    monkeypatch.setattr(discovery, "related_terms", lambda _c, term, limit=10: related.get(term, []))

    body = client.get("/api/discover?offset=0&limit=25", headers=CRON).json()

    assert written["rejected"] == ["p1"]
    assert body["duplicates_rejected"] == 1
    keywords = [c["keyword"] for c in written["inserted"]]
    # cat toy (rejeitado), dragon eggs (repete o anterior) e chess set (ja pendente) ficam de fora;
    # no maximo DISCOVER_PER_SEED por semente.
    assert keywords == ["3d printed dragon egg", "fidget spinner", "marble run", "night light"]
    assert written["inserted"][0]["name"] == "Dragon Egg"
    assert written["inserted"][0]["category"] == "brinquedos"
    assert all(c["status"] == "pending" for c in written["inserted"])


def test_cron_diario_roda_as_sementes(api, monkeypatch):
    client, _ = api
    explored = []
    monkeypatch.setattr(discovery, "related_terms", lambda _c, term, limit=10: explored.append(term) or [])

    class Day:
        value = date(2026, 9, 16)

        @classmethod
        def today(cls):
            return cls.value

    monkeypatch.setattr(index, "date", Day)
    client.get("/api/discover?limit=2", headers=CRON)
    first = list(explored)
    explored.clear()
    Day.value += timedelta(days=1)
    client.get("/api/discover?limit=2", headers=CRON)
    assert first and explored and first != explored


def test_lista_de_candidatos_esconde_variacoes(api, monkeypatch):
    client, _ = api
    from core import auth

    monkeypatch.setattr(auth, "viewer_from_authorization", lambda _h: auth.Viewer(user_id="a", is_admin=True))
    names = [c["keyword"] for c in client.get("/api/candidates", headers={"Authorization": "Bearer x"}).json()["candidates"]]
    assert names == ["chess set"]


def test_recolha_poe_ativos_primeiro_e_ignora_rejeitados(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "segredo")
    rows = [row("a pending", "pending"), row("b rejected", "rejected"), row("c archived", "archived"), row("d active")]
    monkeypatch.setattr(db, "fetch_model_rows", lambda *a, **k: rows)
    monkeypatch.setattr(sources, "http_client", FakeClient)
    monkeypatch.setattr(sources, "collect", lambda model, _c: sources.Signal(demand_raw=1.0))
    saved = []
    monkeypatch.setattr(db, "save_snapshots", lambda snaps: saved.extend(s["model_id"] for s in snaps) or len(snaps))

    TestClient(index.app).get("/api/collect", headers=CRON)
    assert saved == ["d active", "c archived", "a pending"]
