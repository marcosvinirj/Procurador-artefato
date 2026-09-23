"""Conectores de sinais de mercado.

Regras que qualquer conector novo tem de respeitar:
  - timeout curto (a funcao do cron tem ~10s no total);
  - falhar sozinho: devolve None, nunca levanta, nunca derruba a recolha;
  - nunca inventar valores — sem dados, o componente fica em falta e o score
    redistribui o peso (ver core/scoring._weighted).
"""

from __future__ import annotations

import html
import json
import math
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
ETSY_LISTINGS_BATCH_ENDPOINT = "https://openapi.etsy.com/v3/application/listings/batch"
ETSY_LISTING_REVIEWS_ENDPOINT = "https://openapi.etsy.com/v3/application/listings/{listing_id}/reviews"
TRENDS_EXPLORE = "https://trends.google.com/trends/api/explore"
TRENDS_TIMESERIES = "https://trends.google.com/trends/api/widgetdata/multiline"
EBAY_TOKEN_ENDPOINT = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_SEARCH_ENDPOINT = "https://api.ebay.com/buy/browse/v1/item_summary/search"
YOUTUBE_SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"


SHOWCASE_SIZE = 4  # o Premium ve os 4 primeiros anuncios; o Pro, so o lider


@dataclass(frozen=True)
class Signal:
    demand_raw: float | None = None
    competition_raw: float | None = None
    margin_est: float | None = None
    showcase: tuple[dict[str, Any], ...] = ()


def terms_for(model: dict[str, Any]) -> list[str]:
    """Palavra-chave + sinonimos: um mesmo produto vende sob varios nomes e
    ignora-los subestimaria tanto a procura como a concorrencia."""
    synonyms = [s for s in (model.get("synonyms") or []) if s]
    return [model["keyword"], *synonyms][:MAX_TERMS]


def etsy_market(
    client: httpx.Client, terms: Sequence[str]
) -> tuple[float | None, float | None, tuple[dict[str, Any], ...]]:
    """Saturacao (nr. de listagens ativas), proxy de margem (preco mediano do
    topo) e a vitrine: os primeiros anuncios do termo mais concorrido.

    A vitrine nao entra no score. O primeiro anuncio e reaproveitado por
    review_velocity (precisa de uma listagem concreta para perguntar "quantas
    avaliacoes novas"), e os outros so se mostram, conforme o plano. Vem da
    mesma busca: nenhum pedido a mais. A foto nao vem nesta resposta da Etsy —
    junta-se depois, em lote (etsy_images).

    Requer ETSY_API_KEY (endpoint app-level da API v3, sem OAuth). Sem chave
    devolve (None, None, ()) — o sinal fica em falta, nao a zero.
    """
    key = os.environ.get("ETSY_API_KEY")
    if not key:
        return None, None, ()

    best_count: float | None = None
    best_price: float | None = None
    best_showcase: tuple[dict[str, Any], ...] = ()
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
            results = payload.get("results") or []
            best_price = _median_price(results)
            best_showcase = _showcase(results)
    return best_count, best_price, best_showcase


def _showcase(listings: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Os primeiros do sort_on=score, os mais relevantes da busca. So o que se
    mostra; o link so passa se for mesmo da Etsy (vai para um href no site)."""
    showcase = []
    for listing in listings:
        listing_id, url = listing.get("listing_id"), listing.get("url")
        if not isinstance(listing_id, int) or not isinstance(url, str):
            continue
        if not url.startswith("https://www.etsy.com/listing/"):
            continue
        price = listing.get("price") or {}
        amount, divisor, currency = price.get("amount"), price.get("divisor"), price.get("currency_code")
        valid = isinstance(amount, int) and isinstance(divisor, int) and divisor > 0
        showcase.append(
            {
                "listing_id": listing_id,
                "title": html.unescape(str(listing.get("title") or ""))[:140],
                "url": url.split("?")[0],
                "price": round(amount / divisor, 2) if valid else None,
                "currency": currency if isinstance(currency, str) else None,
            }
        )
        if len(showcase) == SHOWCASE_SIZE:
            break
    return tuple(showcase)


def etsy_images(client: httpx.Client, listing_ids: Sequence[int]) -> dict[int, str]:
    """listing_id -> foto principal (570px), ate 100 anuncios por pedido. A
    foto e da Etsy e fica la (o site so aponta para ela, nunca a copia). So
    passa um endereco do CDN de imagens da Etsy. Falha devolve {}."""
    key = os.environ.get("ETSY_API_KEY")
    if not key or not listing_ids:
        return {}
    try:
        response = client.get(
            ETSY_LISTINGS_BATCH_ENDPOINT,
            params={"listing_ids": ",".join(str(i) for i in listing_ids[:100]), "includes": "Images"},
            headers={"x-api-key": key},
        )
        response.raise_for_status()
        results = response.json().get("results") or []
    except (httpx.HTTPError, ValueError, AttributeError):
        return {}
    images = {}
    for listing in results:
        photos = sorted(listing.get("images") or [], key=lambda image: image.get("rank") or 99)
        url = photos[0].get("url_570xN") if photos else None
        listing_id = listing.get("listing_id")
        if isinstance(listing_id, int) and isinstance(url, str) and url.startswith("https://i.etsystatic.com/"):
            images[listing_id] = url
    return images


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


def youtube_interest(client: httpx.Client, terms: Sequence[str]) -> float | None:
    """Atencao no YouTube para o termo, mapeada para 0..100 — proxy de atencao
    real (quem ja gasta tempo a ver conteudo sobre isto), diferente do Google
    Trends, que mede so intencao de pesquisa.

    O mapeamento logaritmico NAO e cosmetico: `demand_raw` e comparado por
    percentil dentro da categoria, e o Trends vive em 0..100. Devolver
    visualizacoes em bruto (milhoes) poria qualquer modelo que caisse nesta
    reserva no topo da categoria so pela diferenca de unidade, nao por merito
    — um numero errado, pior do que sinal nenhum. Ver _views_to_band.

    Requer YOUTUBE_API_KEY (YouTube Data API v3, gratuita, sem OAuth). So o
    primeiro termo: a quota gratuita e 10 000 unidades/dia e uma busca
    (search.list) custa 100 — nao da para gastar 2 por modelo em todos.
    Zero videos encontrados e um dado real (0.0), nao ausencia de dado; falha
    de rede ou de quota devolve None.
    """
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key or not terms:
        return None
    try:
        search = client.get(
            YOUTUBE_SEARCH_ENDPOINT,
            params={"part": "id", "q": terms[0], "type": "video", "maxResults": 5, "key": key},
        )
        search.raise_for_status()
        video_ids = [item["id"]["videoId"] for item in search.json().get("items", [])]
        if not video_ids:
            return 0.0

        videos = client.get(
            YOUTUBE_VIDEOS_ENDPOINT,
            params={"part": "statistics", "id": ",".join(video_ids), "key": key},
        )
        videos.raise_for_status()
        views = []
        for item in videos.json().get("items", []):
            # viewCount pode faltar ou vir null (criador esconde a contagem);
            # um video assim conta 0, nao derruba a soma dos outros.
            try:
                views.append(int(item["statistics"]["viewCount"]))
            except (KeyError, TypeError, ValueError):
                continue
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None
    return _views_to_band(sum(views))


# 10M visualizacoes somadas no top-5 = topo da banda. Logaritmico porque a
# atencao no YouTube distribui-se por ordens de grandeza: a diferenca entre
# 1k e 100k importa muito mais do que entre 5M e 5.1M.
YOUTUBE_BAND_CEILING_LOG = 7.0  # log10(10_000_000)


def _views_to_band(views: int) -> float:
    """Visualizacoes -> 0..100, a mesma banda do Google Trends.

    Aproximacao assumida: nao torna as duas fontes semanticamente iguais
    (indice de interesse relativo vs. volume absoluto), so impede que a
    diferenca de unidade decida sozinha o ranking.
    """
    return min(100.0, math.log10(views + 1) / YOUTUBE_BAND_CEILING_LOG * 100.0)


REVIEW_WINDOW_DAYS = 30
# A maioria das listagens leva 0-20 avaliacoes/mes; poucas, centenas. Log10,
# mesma familia do _views_to_band, para um outlier nao decidir sozinho a
# categoria. 200/mes no topo da banda: acima disso ja e um best-seller claro.
REVIEW_BAND_CEILING_LOG = 2.3  # log10(200)


def _reviews_to_band(count: int) -> float:
    return min(100.0, math.log10(count + 1) / REVIEW_BAND_CEILING_LOG * 100.0)


def review_velocity(client: httpx.Client, listing_id: str | None) -> float | None:
    """Procura de compra real: avaliacoes novas na listagem lider do termo, nos
    ultimos REVIEW_WINDOW_DAYS dias. Quem avalia, comprou — diferente do Trends
    (intencao de pesquisa) e do YouTube (atencao passiva), que so servem de
    proxy quando este falta.

    Recebe o listing_id que etsy_market ja obteve, nao os termos: pedir uma
    listagem concreta e uma segunda busca por keyword custariam dois pedidos
    Etsy por termo em vez de um. Requer ETSY_API_KEY (endpoint app-level da
    API v3 de avaliacoes por listagem, sem OAuth — a mesma chave do
    etsy_market). Sem listagem (Etsy indisponivel ou termo sem resultados) ou
    sem chave, devolve None: falta de sinal, nao zero. Zero avaliacoes na
    janela e um dado real (0.0) — a listagem existe, so nao vendeu no periodo.
    """
    key = os.environ.get("ETSY_API_KEY")
    if not key or not listing_id:
        return None
    since = int(time.time()) - REVIEW_WINDOW_DAYS * 86400
    try:
        response = client.get(
            ETSY_LISTING_REVIEWS_ENDPOINT.format(listing_id=listing_id),
            params={"limit": 1, "min_created": since},
            headers={"x-api-key": key},
        )
        response.raise_for_status()
        count = response.json().get("count")
    except (httpx.HTTPError, ValueError):
        return None
    return _reviews_to_band(int(count)) if isinstance(count, (int, float)) else None


def collect(model: dict[str, Any], client: httpx.Client) -> Signal:
    """Compoe os conectores num sinal. Um conector que falhe nao afeta os outros."""
    terms = terms_for(model)
    competition, margin, showcase = etsy_market(client, terms)
    if competition is None or margin is None:
        ebay_competition, ebay_margin = ebay_market(client, terms)  # fallback quando o Etsy falta
        competition = ebay_competition if competition is None else competition
        margin = ebay_margin if margin is None else margin
    demand = review_velocity(client, str(showcase[0]["listing_id"]) if showcase else None)
    if demand is None:
        demand = google_trends_interest(client, terms)  # proxy enquanto o real nao liga
    if demand is None:
        demand = youtube_interest(client, terms)  # reserva quando o Trends falha/bloqueia
    return Signal(demand_raw=demand, competition_raw=competition, margin_est=margin, showcase=showcase)


def http_client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
