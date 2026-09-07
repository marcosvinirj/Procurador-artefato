"""Conectores de sinais de mercado.

Regras que qualquer conector novo tem de respeitar:
  - timeout curto (a funcao do cron tem ~10s no total);
  - falhar sozinho: devolve None, nunca levanta, nunca derruba a recolha;
  - nunca inventar valores — sem dados, o componente fica em falta e o score
    redistribui o peso (ver core/scoring._weighted).
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from statistics import median
from typing import Any, Sequence

import httpx

TIMEOUT = httpx.Timeout(3.0, connect=2.0)
# So os termos mais fortes: cada termo e um round-trip, e o orcamento e apertado.
MAX_TERMS = 2
USER_AGENT = "TrendPrint/1.0 (+https://github.com/trendprint)"

ETSY_ENDPOINT = "https://openapi.etsy.com/v3/application/listings/active"
TRENDS_EXPLORE = "https://trends.google.com/trends/api/explore"
TRENDS_TIMESERIES = "https://trends.google.com/trends/api/widgetdata/multiline"
EBAY_TOKEN_ENDPOINT = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_SEARCH_ENDPOINT = "https://api.ebay.com/buy/browse/v1/item_summary/search"


@dataclass(frozen=True)
class Signal:
    demand_raw: float | None = None
    competition_raw: float | None = None
    margin_est: float | None = None


def terms_for(model: dict[str, Any]) -> list[str]:
    """Palavra-chave + sinonimos: um mesmo produto vende sob varios nomes e
    ignora-los subestimaria tanto a procura como a concorrencia."""
    synonyms = [s for s in (model.get("synonyms") or []) if s]
    return [model["keyword"], *synonyms][:MAX_TERMS]


def etsy_market(client: httpx.Client, terms: Sequence[str]) -> tuple[float | None, float | None]:
    """Saturacao (nr. de listagens ativas) e proxy de margem (preco mediano do topo).

    Requer ETSY_API_KEY (endpoint app-level da API v3, sem OAuth). Sem chave
    devolve (None, None) — o sinal fica em falta, nao a zero.
    """
    key = os.environ.get("ETSY_API_KEY")
    if not key:
        return None, None

    best_count: float | None = None
    best_price: float | None = None
    for term in terms:
        try:
            response = client.get(
                ETSY_ENDPOINT,
                params={"keywords": term, "limit": 25, "sort_on": "score"},
                headers={"x-api-key": key},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            continue

        count = payload.get("count")
        if not isinstance(count, (int, float)):
            continue
        # O termo mais saturado manda: e o piso real de concorrencia do produto.
        if best_count is None or count > best_count:
            best_count = float(count)
            best_price = _median_price(payload.get("results") or [])
    return best_count, best_price


def _median_price(listings: Sequence[dict[str, Any]]) -> float | None:
    prices = []
    for listing in listings:
        price = listing.get("price") or {}
        amount, divisor = price.get("amount"), price.get("divisor")
        if isinstance(amount, (int, float)) and isinstance(divisor, (int, float)) and divisor:
            prices.append(amount / divisor)
    return _median(prices)


def _median(values: Sequence[float]) -> float | None:
    return median(values) if values else None


# Cache em memoria do processo, nao entre dias: um token dura ~2h (expires_in
# real da eBay), mas uma recolha demora segundos — sem isto, cada modelo que
# precisasse do fallback pediria o seu proprio token, so para o desperdicar.
# Threads da recolha partilham este cache; o lock evita duas a pedir ao mesmo
# tempo no arranque a frio.
_ebay_token_lock = threading.Lock()
_ebay_token_cache: dict[str, Any] = {}


def _ebay_token(client: httpx.Client) -> str | None:
    """Token app-level OAuth2 (client-credentials), cacheado para a recolha inteira."""
    client_id = os.environ.get("EBAY_CLIENT_ID")
    client_secret = os.environ.get("EBAY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    with _ebay_token_lock:
        cached = _ebay_token_cache.get("token")
        if cached and _ebay_token_cache.get("expires_at", 0.0) > time.monotonic():
            return cached

        try:
            response = client.post(
                EBAY_TOKEN_ENDPOINT,
                data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
                auth=(client_id, client_secret),
            )
            response.raise_for_status()
            body = response.json()
            token, expires_in = body.get("access_token"), body.get("expires_in", 0)
        except (httpx.HTTPError, ValueError, KeyError):
            return None

        if not isinstance(token, str):
            return None
        # margem de seguranca: renova um pouco antes do fim real, para nunca
        # usar um token que expire a meio de um pedido em curso.
        _ebay_token_cache["token"] = token
        _ebay_token_cache["expires_at"] = time.monotonic() + max(0, expires_in - 60)
        return token


def ebay_market(client: httpx.Client, terms: Sequence[str]) -> tuple[float | None, float | None]:
    """Saturacao (nr. de resultados) e proxy de margem (preco mediano do topo).

    Segundo sinal de concorrencia/margem, o mesmo papel que etsy_market ja
    cumpre — serve de fallback quando o Etsy falha ou a chave nao esta
    configurada. So conta anuncios novos e de preco fixo, para ficar
    comparavel ao Etsy (leilao e usado nao sao o mesmo mercado). Requer
    EBAY_CLIENT_ID e EBAY_CLIENT_SECRET; sem alguma delas devolve (None, None)
    sem tentar rede.
    """
    token = _ebay_token(client)
    if not token:
        return None, None

    best_count: float | None = None
    best_price: float | None = None
    for term in terms:
        try:
            response = client.get(
                EBAY_SEARCH_ENDPOINT,
                # so novo e preco fixo: leilao e usado nao sao comparaveis a
                # uma listagem do Etsy e distorceriam a concorrencia/mediana.
                params={"q": term, "limit": 25, "filter": "conditions:{NEW},buyingOptions:{FIXED_PRICE}"},
                headers={
                    "Authorization": f"Bearer {token}",
                    # obrigatorio no Browse API; US para bater certo com o
                    # mercado que o Google Trends ja usa (geo="US").
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            continue

        total = payload.get("total")
        if not isinstance(total, (int, float)):
            continue
        # O termo mais saturado manda: e o piso real de concorrencia do produto.
        if best_count is None or total > best_count:
            best_count = float(total)
            best_price = _median(_item_prices(payload.get("itemSummaries") or []))
    return best_count, best_price


def _item_prices(items: Sequence[dict[str, Any]]) -> list[float]:
    prices = []
    for item in items:
        value = (item.get("price") or {}).get("value")
        try:
            prices.append(float(value))
        except (TypeError, ValueError):
            continue
    return prices


def google_trends_interest(client: httpx.Client, terms: Sequence[str]) -> float | None:
    """Interesse de pesquisa mais recente (0..100) para o termo principal.

    Endpoint publico e nao-oficial do Google Trends: duas chamadas (token +
    serie) e resposta com prefixo anti-JSONP. Pode ser bloqueado a partir de
    IPs de datacenter — nesse caso devolve None em silencio.
    """
    if not terms:
        return None
    request = {
        "comparisonItem": [{"keyword": terms[0], "geo": "US", "time": "today 3-m"}],
        "category": 0,
        "property": "",
    }
    try:
        explore = client.get(
            TRENDS_EXPLORE, params={"hl": "en-US", "tz": "0", "req": json.dumps(request)}
        )
        explore.raise_for_status()
        widgets = json.loads(explore.text[4:])["widgets"]
        widget = next(w for w in widgets if w.get("id") == "TIMESERIES")

        series = client.get(
            TRENDS_TIMESERIES,
            params={
                "hl": "en-US",
                "tz": "0",
                "req": json.dumps(widget["request"]),
                "token": widget["token"],
            },
        )
        series.raise_for_status()
        points = json.loads(series.text[5:])["default"]["timelineData"]
    except (httpx.HTTPError, ValueError, KeyError, IndexError, StopIteration):
        return None

    settled = [p for p in points if not p.get("isPartial")] or points
    if not settled:
        return None
    return float(settled[-1]["value"][0])


def review_velocity(client: httpx.Client, terms: Sequence[str]) -> float | None:
    """Procura de compra real: ritmo de avaliacoes novas nas listagens de topo.

    POR LIGAR — exige OAuth Etsy e uma chamada por listagem, o que nao cabe no
    orcamento de 10s do cron. Devolve None de proposito: melhor um sinal em
    falta do que um numero inventado.
    """
    return None


def collect(model: dict[str, Any], client: httpx.Client) -> Signal:
    """Compoe os conectores num sinal. Um conector que falhe nao afeta os outros."""
    terms = terms_for(model)
    competition, margin = etsy_market(client, terms)
    if competition is None or margin is None:
        ebay_competition, ebay_margin = ebay_market(client, terms)  # fallback quando o Etsy falta
        competition = ebay_competition if competition is None else competition
        margin = ebay_margin if margin is None else margin
    demand = review_velocity(client, terms)
    if demand is None:
        demand = google_trends_interest(client, terms)  # proxy enquanto o real nao liga
    return Signal(demand_raw=demand, competition_raw=competition, margin_est=margin)


def http_client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
