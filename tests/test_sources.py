"""Conectores de mercado. O que nao pode falhar: um conector em baixo devolve
None (sinal em falta), nunca zero nem um numero de outra escala."""

import json

import httpx
import pytest

from core import sources


class FakeEtsy:
    """Responde a busca de listagens e a avaliacoes por listagem."""

    def __init__(self, search=None, reviews=None, boom=False):
        self.search, self.reviews, self.boom = search, reviews, boom
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params=None, headers=None):
        self.calls.append((url, params or {}))
        if self.boom:
            raise httpx.ConnectTimeout("sem rede")
        payload = self.reviews if "/reviews" in url else self.search
        request = httpx.Request("GET", url)
        if payload is None:
            return httpx.Response(500, text="erro", request=request)
        return httpx.Response(200, text=json.dumps(payload), request=request)

    def close(self):
        pass


def listing(listing_id, amount):
    return {"listing_id": listing_id, "price": {"amount": amount, "divisor": 100}}


@pytest.fixture(autouse=True)
def chave(monkeypatch):
    monkeypatch.setenv("ETSY_API_KEY", "keystring:secret")


def test_etsy_market_devolve_a_listagem_lider_do_termo_mais_saturado():
    """O criterio e o mesmo da concorrencia: manda o termo com mais listagens."""
    client = FakeEtsy(search={"count": 900, "results": [listing(111, 2500), listing(222, 1500)]})
    competition, margin, listing_id = sources.etsy_market(client, ["dice tray"])
    assert (competition, margin, listing_id) == (900.0, 20.0, "111")


def test_etsy_market_sem_chave_nao_inventa(monkeypatch):
    monkeypatch.delenv("ETSY_API_KEY")
    assert sources.etsy_market(FakeEtsy(), ["dice tray"]) == (None, None, None)


def test_etsy_market_sem_resultados_nao_tem_listagem():
    client = FakeEtsy(search={"count": 0, "results": []})
    assert sources.etsy_market(client, ["produto inexistente"]) == (0.0, None, None)


def test_avaliacoes_da_janela_viram_banda():
    client = FakeEtsy(reviews={"count": 12, "results": []})
    valor = sources.review_velocity(client, "111")
    assert valor == pytest.approx(sources._reviews_to_band(12))
    assert 0 < valor < 100

    url, params = client.calls[0]
    assert url.endswith("/listings/111/reviews")
    assert params["limit"] == 1  # so o campo count interessa; nao puxar historico
    assert params["min_created"] > 0


def test_zero_avaliacoes_e_dado_real_nao_ausencia():
    """A listagem existe e nao vendeu na janela: 0.0 e informacao, None nao."""
    assert sources.review_velocity(FakeEtsy(reviews={"count": 0}), "111") == 0.0


@pytest.mark.parametrize(
    "client,listing_id",
    [
        (FakeEtsy(reviews={"count": 5}), None),  # Etsy nao deu listagem nenhuma
        (FakeEtsy(boom=True), "111"),  # rede em baixo
        (FakeEtsy(reviews=None), "111"),  # HTTP 500
        (FakeEtsy(reviews={"sem": "count"}), "111"),  # resposta estranha
        (FakeEtsy(reviews={"count": "muitas"}), "111"),  # count nao numerico
    ],
)
def test_falha_devolve_none_nunca_zero(client, listing_id):
    assert sources.review_velocity(client, listing_id) is None


def test_sem_chave_nao_pede_avaliacoes(monkeypatch):
    monkeypatch.delenv("ETSY_API_KEY")
    client = FakeEtsy(reviews={"count": 99})
    assert sources.review_velocity(client, "111") is None
    assert client.calls == []


@pytest.mark.parametrize("count,esperado", [(0, 0.0), (200, 100.0), (5000, 100.0)])
def test_banda_fica_entre_0_e_100(count, esperado):
    assert sources._reviews_to_band(count) == pytest.approx(esperado, abs=0.5)


def test_banda_cresce_com_as_avaliacoes():
    bandas = [sources._reviews_to_band(n) for n in (0, 1, 10, 50, 200)]
    assert bandas == sorted(bandas)


def test_collect_usa_a_listagem_da_busca_para_as_avaliacoes(monkeypatch):
    """A procura vem das avaliacoes; Trends e YouTube so entram se isso falhar."""
    monkeypatch.setattr(sources, "etsy_market", lambda *_: (900.0, 20.0, "111"))
    vistos = []
    monkeypatch.setattr(
        sources, "review_velocity", lambda _c, listing_id: vistos.append(listing_id) or 42.0
    )
    monkeypatch.setattr(sources, "google_trends_interest", lambda *_: pytest.fail("nao devia chegar aqui"))

    signal = sources.collect({"keyword": "dice tray", "synonyms": []}, FakeEtsy())
    assert vistos == ["111"]
    assert signal == sources.Signal(demand_raw=42.0, competition_raw=900.0, margin_est=20.0)


def test_collect_cai_para_o_trends_quando_nao_ha_avaliacoes(monkeypatch):
    monkeypatch.setattr(sources, "etsy_market", lambda *_: (900.0, 20.0, None))
    monkeypatch.setattr(sources, "review_velocity", lambda *_: None)
    monkeypatch.setattr(sources, "google_trends_interest", lambda *_: 31.0)

    signal = sources.collect({"keyword": "dice tray", "synonyms": []}, FakeEtsy())
    assert signal.demand_raw == 31.0
