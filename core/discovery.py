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

SUGGEST_URL = "https://suggestqueries.google.com/complete/search"

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
    ("3d printed anime", "geek"),
    ("3d printed dnd", "geek"),
    ("3d printed cosplay", "geek"),
    ("3d printed miniatures", "geek"),
)
SOURCE = "google_suggest"
# Fontes antigas: sem filtro de impressao 3D (google_trends_related) ou de uma
# fonte que devolvia vazio (google_trends_3d). Os pendentes delas sao rejeitados.
LEGACY_SOURCES = frozenset({"google_trends_related", "google_trends_3d"})

PRINT_WORDS = frozenset("3d printed printable print prints printing printer printers".split())
# Basta uma destas para a consulta nao ser um produto: pergunta, loja, site,
# pais ou tutorial ("how to paint miniatures", "toys amazon", "miniatures uk").
JUNK = frozenset(
    """how what why when where which who whose vs versus meaning worth safe legal tutorial guide
    review reviews software slicer filament settings profile business money sell selling shop store
    amazon etsy reddit thingiverse printables makerworld cults ebay temu aliexpress walmart shein
    can do does is are you your my i make making paint painting largest biggest smallest most popular
    famous common useful practical
    uk usa us australia canada india china europe germany japan brasil brazil singapore nz zealand
    ireland africa philippines malaysia mexico spain france italy kmart target ikea costco wish
    sale price near""".split()
)
# Enfeite de pesquisa: sai do nome guardado ("best 3d printed dragon stl" -> "dragon").
FILLER = frozenset(
    """stl file files free diy custom best cool cute easy cheap top idea ideas me
    item items product products stuff thing things design designs model models project projects
    accessory accessories system setup""".split()
)
GRAMMAR = frozenset("for the a an and with of to in on".split())
# Palavras que nao distinguem um produto de outro (so para comparar).
NOISE = PRINT_WORDS | FILLER | GRAMMAR | JUNK | frozenset(
    "gift gifts kid kids him her men women boy boys girl girls adult adults beginner beginners teen teens".split()
)
# O mesmo objeto com outro nome: "iphone 18 case" e uma "phone case".
ALIASES = {
    "iphone": "phone", "smartphone": "phone", "cellphone": "phone", "cell": "phone",
    "airpod": "earbud", "earphone": "earbud", "flexible": "flexi", "mini": "miniature",
}


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
    if JUNK & set(words):
        return None
    words = [w for w in words if w not in PRINT_WORDS and w not in FILLER]
    while words and words[0] in GRAMMAR:
        words.pop(0)
    while words and words[-1] in GRAMMAR:
        words.pop()
    product = " ".join(words)
    # Uma palavra so e categoria, nao produto ("office", "table"): nao serve de
    # termo de mercado. Os produtos de uma palavra entram a mao, no seed.
    return product if len(tokens(product)) >= 2 else None


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
    """Ids dos pendentes a rejeitar: os das fontes antigas e os que repetem algo
    ja conhecido, ou outro pendente mais generico — entre dois, fica o de menos
    palavras (e, no empate, o mais curto)."""
    known = known_terms(others)
    ids = []
    for row in sorted(pending, key=lambda r: (len(tokens(r["keyword"])), len(r["keyword"]))):
        if row.get("source") in LEGACY_SOURCES or is_variant(row["keyword"], known):
            ids.append(row["id"])
        else:
            known.append(tokens(row["keyword"]))
    return ids


def suggested_terms(client: httpx.Client, seed: str, limit: int = 10) -> list[str]:
    """O que as pessoas escrevem a seguir a `seed` no Google (autocompletar).

    Substituiu as "pesquisas relacionadas" do Trends, que devolvem vazio para
    termos de nicho ("moon lamp", "3d printed dnd") e lixo generico para termos
    muito populares — por isso a descoberta nunca propunha nada. A direcao da
    procura continua a vir do Trends, em core/sources.py, que funciona.

    Endpoint publico, sem chave. Falha isolada: devolve [] em silencio.
    """
    try:
        response = client.get(
            SUGGEST_URL, params={"client": "firefox", "hl": "en", "q": f"{seed} "}
        )
        response.raise_for_status()
        suggestions = json.loads(response.text)[1]
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        return []
    return [s for s in suggestions if isinstance(s, str)][:limit]
