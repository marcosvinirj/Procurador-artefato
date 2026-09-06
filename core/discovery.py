"""Descoberta de candidatos a modelo — encontra termos novos, nao mede sinais
de um termo existente (isso e o papel de core/sources.py).

Um candidato descoberto nunca entra direto no ranking publico: fica com
status='pending' ate um humano aprovar ou rejeitar (ver api/index.py). Isto
evita que o site se encha de produtos irrelevantes ou duplicados sem controlo.
"""

from __future__ import annotations

import json

import httpx

TRENDS_EXPLORE = "https://trends.google.com/trends/api/explore"
TRENDS_RELATED = "https://trends.google.com/trends/api/widgetdata/relatedsearches"


def related_terms(client: httpx.Client, seed: str, limit: int = 5) -> list[str]:
    """Consultas relacionadas ao `seed` no Google Trends, priorizando as "em
    ascensao" (mercado a nascer, nao um pico ja capturado por todos). Sem
    ascensao suficiente, cai para as mais fortes. Mesmo endpoint publico e sem
    chave que ja usamos para a tendencia — falha isolada, devolve [] em silencio.
    """
    request = {
        "comparisonItem": [{"keyword": seed, "geo": "US", "time": "today 3-m"}],
        "category": 0,
        "property": "",
    }
    try:
        explore = client.get(TRENDS_EXPLORE, params={"hl": "en-US", "tz": "0", "req": json.dumps(request)})
        explore.raise_for_status()
        widgets = json.loads(explore.text[4:])["widgets"]
        widget = next(w for w in widgets if w.get("id") == "RELATED_QUERIES")

        related = client.get(
            TRENDS_RELATED,
            params={"hl": "en-US", "tz": "0", "req": json.dumps(widget["request"]), "token": widget["token"]},
        )
        related.raise_for_status()
        ranked_lists = json.loads(related.text[5:])["default"]["rankedList"]
    except (httpx.HTTPError, ValueError, KeyError, IndexError, StopIteration):
        return []

    # rankedList[0] = "top", rankedList[1] = "rising" quando existe.
    rising = ranked_lists[1]["rankedKeyword"] if len(ranked_lists) > 1 else []
    top = ranked_lists[0]["rankedKeyword"] if ranked_lists else []
    queries = [k["query"] for k in (rising or top) if isinstance(k.get("query"), str)]
    return queries[:limit]
