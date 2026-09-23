"""Vigia de lojas da Etsy — segunda fonte de descoberta, ao lado do
autocompletar do Google (core/discovery.py).

Pergunta: das lojas que o admin escolheu vigiar, que produto lancado ha pouco
ja esta a vender? Sinal: listagem criada nos ultimos NEW_LISTING_DAYS que
recebeu pelo menos MIN_REVIEWS avaliacoes nos ultimos REVIEW_WINDOW_DAYS.
Quem avalia, comprou. A avaliacao subamostra (so parte dos compradores avalia)
e chega dias depois da venda: serve para ritmo, nao para contar vendas.

O que este sinal nao ve: visualizacoes de listagens alheias (so o dono as ve)
e produtos que explodem fora da Etsy (TikTok) e ainda nao chegaram la.

Diferenca de proposito face ao discovery: aqui NAO se exige "3d printed" no
titulo. Numa loja de impressao 3D o comprador ja sabe o que compra e o titulo
raramente o diz; a garantia de que e peca impressa e a loja estar na lista.

Tudo com ETSY_API_KEY: findShops, findAllActiveListingsByShop e
getReviewsByShop herdam a seguranca global api_key da API v3 (verificado na
especificacao oficial, openapi/generated/oas/3.0.0.json). Dois pedidos por loja.
"""

from __future__ import annotations

import html
import os
import re
from collections import Counter
from typing import Any

import httpx

from core import discovery

ETSY_SHOPS = "https://openapi.etsy.com/v3/application/shops"
ETSY_SHOP_LISTINGS = "https://openapi.etsy.com/v3/application/shops/{shop_id}/listings/active"
ETSY_SHOP_REVIEWS = "https://openapi.etsy.com/v3/application/shops/{shop_id}/reviews"

SOURCE = "etsy_shop"
DAY = 86_400
NEW_LISTING_DAYS = 120  # "lancado ha pouco": listagens dos ultimos ~4 meses
REVIEW_WINDOW_DAYS = 30
# Uma avaliacao isolada pode ser um amigo; duas num mes, numa listagem nova,
# ja sao varias vendas (so uma fracao dos compradores avalia).
MIN_REVIEWS = 2
MAX_TERM_WORDS = 4

# Nomes de loja da Etsy: so letras e numeros. Validar antes de ir a API evita
# mandar lixo (ou um link inteiro) como parametro.
SHOP_NAME = re.compile(r"^[A-Za-z0-9]{2,40}$")
SHOP_URL = re.compile(r"etsy\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?shop/([A-Za-z0-9]+)", re.IGNORECASE)


def shop_name_from(text: str) -> str | None:
    """"LojaDaAna", "etsy.com/shop/LojaDaAna" ou o link completo -> "LojaDaAna"."""
    text = text.strip()
    match = SHOP_URL.search(text)
    name = match.group(1) if match else text
    return name if SHOP_NAME.match(name) else None


def _headers() -> dict[str, str] | None:
    key = os.environ.get("ETSY_API_KEY")
    return {"x-api-key": key} if key else None


def find_shop(client: httpx.Client, name: str) -> dict[str, Any] | None:
    """Nome -> {"shop_id", "shop_name"}. findShops procura por aproximacao, por
    isso so conta o nome exato (sem diferenca de maiusculas). None se nao
    existir, sem chave, ou se a Etsy falhar."""
    headers = _headers()
    if headers is None:
        return None
    try:
        response = client.get(ETSY_SHOPS, params={"shop_name": name, "limit": 25}, headers=headers)
        response.raise_for_status()
        results = response.json().get("results") or []
    except (httpx.HTTPError, ValueError):
        return None
    for shop in results:
        if str(shop.get("shop_name", "")).lower() == name.lower() and isinstance(shop.get("shop_id"), int):
            return {"shop_id": shop["shop_id"], "shop_name": shop["shop_name"]}
    return None


def _created(listing: dict[str, Any]) -> int:
    value = listing.get("original_creation_timestamp") or listing.get("created_timestamp")
    return value if isinstance(value, int) else 0


def rising_listings(client: httpx.Client, shop_id: int, now: int) -> list[tuple[int, dict[str, Any]]]:
    """[(avaliacoes_na_janela, listagem)] das listagens novas que ja vendem,
    mais avaliadas primeiro. Qualquer falha devolve [] — a loja fica para o
    dia seguinte, nunca derruba as outras."""
    headers = _headers()
    if headers is None:
        return []
    try:
        listings = client.get(
            ETSY_SHOP_LISTINGS.format(shop_id=shop_id),
            params={"sort_on": "created", "sort_order": "desc", "limit": 100},
            headers=headers,
        )
        listings.raise_for_status()
        fresh = [
            item
            for item in listings.json().get("results") or []
            if _created(item) >= now - NEW_LISTING_DAYS * DAY
        ]
        if not fresh:
            return []  # nada lancado ha pouco: poupa o pedido das avaliacoes
        reviews = client.get(
            ETSY_SHOP_REVIEWS.format(shop_id=shop_id),
            params={"limit": 100, "min_created": now - REVIEW_WINDOW_DAYS * DAY},
            headers=headers,
        )
        reviews.raise_for_status()
        counts = Counter(r.get("listing_id") for r in reviews.json().get("results") or [])
    except (httpx.HTTPError, ValueError, AttributeError):
        return []
    rising = [(counts[item.get("listing_id")], item) for item in fresh]
    return sorted((pair for pair in rising if pair[0] >= MIN_REVIEWS), key=lambda pair: -pair[0])


def title_term(title: str) -> str | None:
    """"Chibi Dragon Figure 3D Printed | Desk Decor, Gift" -> "chibi dragon figure".

    O titulo da Etsy e escrito para a pesquisa: o produto vem antes do primeiro
    separador, o resto e enfeite. A API devolve-o com entidades HTML (&#39;).
    No maximo MAX_TERM_WORDS palavras, e pelo menos duas que identifiquem o
    produto — uma so e categoria, a mesma regra do discovery."""
    text = re.sub(r"['’]s\b", "", html.unescape(title))  # "Mom's" -> "Mom", nao "mom s"
    head = re.split(r"\s[-–—|:]\s|[,|(/]", text, maxsplit=1)[0]
    words = [w for w in re.findall(r"[a-z0-9]+", head.lower()) if w not in discovery.NOISE and not w.isdigit()]
    term = " ".join(words[:MAX_TERM_WORDS])
    return term if len(discovery.tokens(term)) >= 2 else None
