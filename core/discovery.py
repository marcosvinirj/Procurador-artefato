"""Descoberta de candidatos a modelo — encontra termos novos, nao mede sinais
de um termo existente (isso e o papel de core/sources.py).

Um candidato descoberto nunca entra direto no ranking publico: fica com
status='pending' ate um humano aprovar ou rejeitar (ver api/index.py). Isto
evita que o site se encha de produtos irrelevantes ou duplicados sem controlo.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Sequence

import httpx

TRENDS_EXPLORE = "https://trends.google.com/trends/api/explore"
TRENDS_RELATED = "https://trends.google.com/trends/api/widgetdata/relatedsearches"

# Sementes genericas por categoria. As sementes por produto ("moon lamp") quase
# so devolvem variacoes do proprio produto ("aquarius moon lamp"); estas trazem
# produtos diferentes ("3d printed dragon egg").
CATEGORY_SEEDS = (
    ("3d printed toys", "brinquedos"),
    ("3d printed home decor", "decoracao"),
    ("3d printed organizer", "utilidades"),
    ("3d printed desk accessories", "gadgets"),
)

# Palavras que nao distinguem um produto de outro.
NOISE = frozenset(
    "3d printed print printing printer stl file files free diy custom for the a an and with of to in on".split()
)


def _singular(word: str) -> str:
    if len(word) > 3 and word.endswith(("xes", "ches", "shes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokens(term: str) -> frozenset[str]:
    """As palavras que identificam o produto: minusculas, no singular, sem ruido."""
    return frozenset(_singular(w) for w in re.findall(r"[a-z0-9]+", term.lower()) if w not in NOISE)


def is_variant(term: str, known: Iterable[frozenset[str]]) -> bool:
    """O mesmo produto dito de outra forma. "aquarius moon lamp" e "moon lamps
    stl" contem "moon lamp"; "lamp" esta contido nele (generico demais). Sem
    palavras que sobrem, tambem conta: ali nao ha produto nenhum."""
    words = tokens(term)
    return not words or any(k <= words or words <= k for k in known)


def known_terms(rows: Sequence[dict[str, Any]]) -> list[frozenset[str]]:
    """Palavra-chave e sinonimos de cada linha, em qualquer estado."""
    terms = [t for row in rows for t in (row["keyword"], *(row.get("synonyms") or ()))]
    return [words for words in map(tokens, terms) if words]


def seeds(rows: Sequence[dict[str, Any]]) -> list[tuple[str, str]]:
    """(termo, categoria) a explorar: as genericas primeiro, depois cada ativo."""
    return [*CATEGORY_SEEDS, *((r["keyword"], r["category"]) for r in rows if r["status"] == "active")]


def display_name(query: str) -> str:
    """"3d printed dragon egg" -> "Dragon Egg". A keyword guarda a consulta inteira."""
    return " ".join(w for w in query.split() if w.lower() not in {"3d", "printed"}).title() or query.title()


def redundant(pending: Sequence[dict[str, Any]], others: Sequence[dict[str, Any]]) -> list[str]:
    """Ids dos pendentes que repetem algo ja conhecido, ou outro pendente mais
    generico — entre dois, fica o de menos palavras (e, no empate, o mais curto)."""
    known = known_terms(others)
    ids = []
    for row in sorted(pending, key=lambda r: (len(tokens(r["keyword"])), len(r["keyword"]))):
        if is_variant(row["keyword"], known):
            ids.append(row["id"])
        else:
            known.append(tokens(row["keyword"]))
    return ids


def related_terms(client: httpx.Client, seed: str, limit: int = 10) -> list[str]:
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
