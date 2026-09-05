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
    return median(prices) if prices else None


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
    demand = review_velocity(client, terms)
    if demand is None:
        demand = google_trends_interest(client, terms)  # proxy enquanto o real nao liga
    return Signal(demand_raw=demand, competition_raw=competition, margin_est=margin)


def http_client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
