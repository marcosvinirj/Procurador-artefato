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

# Toda a busca parte de "3d printed ...": o Google devolve o que as pessoas
# pesquisam JUNTO com o termo, e sem isto vinha de tudo ("iphone 18" a partir
# de "phone case"). As genericas trazem produtos diferentes dos que ja temos.
CATEGORY_SEEDS = (
    ("3d printed toys", "brinquedos"),
    ("3d printed fidget", "brinquedos"),
    ("3d printed home decor", "decoracao"),
    ("3d printed lamp", "decoracao"),
    ("3d printed organizer", "utilidades"),
    ("3d printed kitchen", "utilidades"),
    ("3d printed desk accessories", "gadgets"),
    ("3d printed gaming accessories", "gadgets"),
)
SOURCE = "google_trends_3d"
# Candidatos de antes do filtro de impressao 3D: sem garantia de relevancia.
LEGACY_SOURCE = "google_trends_related"

PRINT_WORDS = frozenset("3d printed print prints printing printer printers".split())
# Enfeite de pesquisa: sai do nome guardado ("best 3d printed dragon stl" -> "dragon").
FILLER = frozenset("stl file files free diy custom best cool cute easy cheap top idea ideas near me".split())
GRAMMAR = frozenset("for the a an and with of to in on".split())
# Palavras que nao distinguem um produto de outro (so para comparar).
NOISE = PRINT_WORDS | FILLER | GRAMMAR | frozenset("gift gifts kid kids him her men women".split())
# O mesmo objeto com outro nome: "iphone 18 case" e uma "phone case".
ALIASES = {"iphone": "phone", "smartphone": "phone", "cellphone": "phone", "airpod": "earbud"}


def _word(word: str) -> str:
    if len(word) > 3 and word.endswith(("xes", "ches", "shes")):
        word = word[:-2]
    elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    return ALIASES.get(word, word)


def tokens(term: str) -> frozenset[str]:
    """As palavras que identificam o produto: minusculas, no singular, sem ruido
    nem numeros de modelo."""
    words = re.findall(r"[a-z0-9]+", term.lower())
    return frozenset(_word(w) for w in words if w not in NOISE and not w.isdigit())


def product_term(query: str) -> str | None:
    """"3d printed dragon egg" -> "dragon egg"; None se a pesquisa nao fala de
    impressao 3D. Guarda-se sem o prefixo, como as keywords que ja existem —
    senao a concorrencia no Etsy sairia noutra escala e o score deixava de ser
    comparavel."""
    words = re.findall(r"[a-z0-9]+", query.lower())
    if "3d" not in words or not any(w.startswith("print") for w in words):
        return None
    words = [w for w in words if w not in PRINT_WORDS and w not in FILLER]
    while words and words[0] in GRAMMAR:
        words.pop(0)
    while words and words[-1] in GRAMMAR:
        words.pop()
    return " ".join(words) or None


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
    active = ((f"3d printed {r['keyword']}", r["category"]) for r in rows if r["status"] == "active")
    return [*CATEGORY_SEEDS, *active]


def rejectable(pending: Sequence[dict[str, Any]], others: Sequence[dict[str, Any]]) -> list[str]:
    """Ids dos pendentes a rejeitar: os da busca antiga (sem filtro de impressao
    3D) e os que repetem algo ja conhecido ou outro pendente mais generico —
    entre dois, fica o de menos palavras (e, no empate, o mais curto)."""
    known = known_terms(others)
    ids = []
    for row in sorted(pending, key=lambda r: (len(tokens(r["keyword"])), len(r["keyword"]))):
        if row.get("source") == LEGACY_SOURCE or is_variant(row["keyword"], known):
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
