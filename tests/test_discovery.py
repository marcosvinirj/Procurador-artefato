"""Descoberta sem duplicados: variacoes de um produto conhecido nunca entram."""

import json
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from api import index
from core import db, discovery, sources
from core.discovery import is_variant, known_terms, product_term, rejectable, tokens

CRON = {"Authorization": "Bearer segredo"}


def row(keyword, status="active", category="decoracao", synonyms=(), rid=None):
    return {"id": rid or keyword, "name": keyword.title(), "keyword": keyword, "category": category,
            "status": status, "synonyms": list(synonyms)}


KNOWN = known_terms(
    [row("moon lamp", synonyms=["luna lamp"]), row("earbud case"), row("phone case"), row("headphone stand")]
)


def test_tokens_ignora_plural_e_ruido():
    assert tokens("3D Printed Moon Lamps STL") == {"moon", "lamp"}
    assert tokens("storage boxes") == tokens("storage box")
    assert tokens("glass vase") == {"glass", "vase"}
    assert tokens("iPhone 18 cases") == tokens("phone case")  # alias + numero de modelo
    assert tokens("flexible axolotl") == tokens("flexi axolotl")
    assert tokens("mini display shelf") == tokens("miniature display shelf")


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
        "iphone 18 case",  # capa de telemovel com outro nome
        "stand for headphones",  # "headphone stand" com as palavras trocadas
    ],
)
def test_variacoes_sao_barradas(term):
    assert is_variant(term, KNOWN)


@pytest.mark.parametrize("term", ["dragon egg", "blunt cases", "3d printed chess set", "lamp shade"])
def test_produtos_diferentes_passam(term):
    assert not is_variant(term, KNOWN)


def pending(keyword, source=discovery.SOURCE):
    return {**row(keyword, "pending"), "source": source}


def test_pendentes_a_rejeitar():
    rows = [
        pending("aquarius moon lamp"),  # variacao de um ativo
        pending("dragon eggs"),  # repete outro pendente: fica o mais curto
        pending("dragon egg"),
        pending("chess set"),
        pending("iphone 18", sorted(discovery.LEGACY_SOURCES)[0]),  # busca antiga, sem filtro 3D
    ]
    assert sorted(rejectable(rows, [row("moon lamp")])) == ["aquarius moon lamp", "dragon eggs", "iphone 18"]


@pytest.mark.parametrize(
    "query,product",
    [
        ("3d printed dragon egg", "dragon egg"),
        ("3D-Printed Chess Set STL", "chess set"),
        ("best 3d print cable clip for desk", "cable clip for desk"),
        ("3d printed toys for kids", None),  # so "toys": categoria, nao produto
        ("free stl 3d printing files", None),  # nada sobra
        ("iphone 18", None),  # nao fala de impressao 3D
        ("3d movie", None),
        ("printed shirt", None),
        ("how to 3d print miniatures", None),  # pergunta
        ("3d printed toys amazon", None),  # loja
        ("3d printed miniatures uk", None),  # pais
        ("3d printed lamp thingiverse", None),  # site de modelos
        ("3d printed office", None),  # uma palavra: categoria
    ],
)
def test_so_pesquisas_de_impressao_3d_viram_produto(query, product):
    assert product_term(query) == product


class FakeClient:
    def close(self):
        pass


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "segredo")
    rows = [
        row("moon lamp"),
        {**row("aquarius moon lamp", "pending", rid="p1"), "source": discovery.SOURCE},  # variacao: rejeitar
        {**row("chess set", "pending", rid="p2"), "source": discovery.SOURCE},  # valido: fica
        {**row("iphone 18", "pending", rid="p3"), "source": sorted(discovery.LEGACY_SOURCES)[0]},  # busca antiga: rejeitar
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
        "3d printed toys": [
            "3d printed toys",  # a propria semente
            "iphone 18",  # nao e impressao 3D
            "3d printed cat toys",  # rejeitado antes: continua conhecido
            "3d printed dragon egg",
            "3d printed dragon eggs",  # repete o anterior
            "3d printed fidget spinner",
            "3d printed chess set",  # ja pendente
            "3d printed toys for kids",  # a semente com enfeite
            "best 3d print marble run stl",
            "3d printed rubber band gun",  # passa do limite por semente
        ],
        "3d printed moon lamp": ["3d printed moon lamp stl", "aquarius moon lamp", "3d printed night light"],
    }
    monkeypatch.setattr(discovery, "suggested_terms", lambda _c, term, limit=10: related.get(term, []))

    body = client.get("/api/discover?offset=0&limit=25", headers=CRON).json()

    assert sorted(written["rejected"]) == ["p1", "p3"]
    assert body["duplicates_rejected"] == 2
    keywords = [c["keyword"] for c in written["inserted"]]
    assert keywords == ["dragon egg", "fidget spinner", "marble run", "night light"]
    assert written["inserted"][0]["name"] == "Dragon Egg"
    assert written["inserted"][0]["category"] == "brinquedos"
    assert written["inserted"][-1]["category"] == "decoracao"
    assert all(c["status"] == "pending" and c["source"] == discovery.SOURCE for c in written["inserted"])


def test_cron_diario_roda_as_sementes(api, monkeypatch):
    client, _ = api
    explored = []
    monkeypatch.setattr(discovery, "suggested_terms", lambda _c, term, limit=10: explored.append(term) or [])

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


class SuggestClient:
    """Responde como o autocompletar do Google: ["consulta", [sugestoes], ...]."""

    def __init__(self, payload, boom=False):
        self.payload, self.boom, self.params = payload, boom, None

    def get(self, url, params):
        if self.boom:
            raise httpx.ConnectTimeout("sem rede")
        self.params = params
        return httpx.Response(200, text=json.dumps(self.payload), request=httpx.Request("GET", url))

    def close(self):
        pass


def test_sugestoes_do_google():
    client = SuggestClient(["3d printed dnd ", ["3d printed dnd miniatures", "3d printed dnd terrain", 7]])
    assert discovery.suggested_terms(client, "3d printed dnd") == [
        "3d printed dnd miniatures",
        "3d printed dnd terrain",
    ]
    assert client.params["q"] == "3d printed dnd "  # o espaco final traz a palavra seguinte


@pytest.mark.parametrize(
    "client",
    [SuggestClient(None, boom=True), SuggestClient(["so a consulta"]), SuggestClient({"nao": "e lista"})],
)
def test_falha_da_fonte_nao_rebenta(client):
    assert discovery.suggested_terms(client, "3d printed dnd") == []


def test_admin_pode_procurar_agora(api, monkeypatch):
    """Botao do painel: mesma descoberta, sem esperar pelo cron."""
    client, written = api
    from core import auth

    monkeypatch.setattr(auth, "viewer_from_authorization", lambda _h: auth.Viewer(user_id="a", is_admin=True))
    # o bloco de sementes do dia varia; repetido em todas, so entra uma vez
    monkeypatch.setattr(discovery, "suggested_terms", lambda _c, _t, limit=10: ["3d printed marble run"])
    body = client.post("/api/admin/discover", headers={"Authorization": "Bearer x"}).json()
    assert body["candidates_proposed"] == 1
    assert [c["keyword"] for c in written["inserted"]] == ["marble run"]
