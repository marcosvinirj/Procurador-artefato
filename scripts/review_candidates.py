"""Revisao local dos candidatos propostos pela descoberta automatica.

So local: usa o CRON_SECRET, que nunca deve ir para o browser (ver CLAUDE.md).
Nao tem dependencias novas — so httpx, ja usado no resto do projeto.

Uso:
    TRENDPRINT_URL=https://procurador-artefato.vercel.app \
    CRON_SECRET=... \
    python scripts/review_candidates.py
"""

from __future__ import annotations

import os
import sys

import httpx

DEFAULT_URL = "https://procurador-artefato.vercel.app"


def main() -> None:
    base_url = os.environ.get("TRENDPRINT_URL", DEFAULT_URL).rstrip("/")
    secret = os.environ.get("CRON_SECRET")
    if not secret:
        sys.exit("Falta CRON_SECRET no ambiente. Ver .env.example.")

    headers = {"Authorization": f"Bearer {secret}"}
    with httpx.Client(base_url=base_url, headers=headers, timeout=15.0) as client:
        candidates = client.get("/api/candidates").raise_for_status().json()["candidates"]

        if not candidates:
            print("Sem candidatos pendentes.")
            return

        print(f"{len(candidates)} candidato(s) por rever:\n")
        for candidate in candidates:
            _review_one(client, candidate)


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:g}"


def _review_one(client: httpx.Client, candidate: dict) -> None:
    print(f"— {candidate['keyword']!r} (categoria sugerida: {candidate['category']}, fonte: {candidate['source']})")
    print(
        f"  procura={_fmt(candidate['demand_raw'])}  "
        f"concorrencia={_fmt(candidate['competition_raw'])}  "
        f"margem={_fmt(candidate['margin_est'])}"
    )
    choice = input("  [a]provar / [r]ejeitar / [s]altar? ").strip().lower()

    if choice == "a":
        name = input(f"  Nome do produto [{candidate['name']}]: ").strip() or candidate["name"]
        category = input(f"  Categoria [{candidate['category']}]: ").strip() or candidate["category"]
        body = {"action": "approve", "name": name, "category": category}
        client.post(f"/api/candidates/{candidate['id']}", json=body).raise_for_status()
        print(f"  aprovado como {name!r}\n")
    elif choice == "r":
        client.post(f"/api/candidates/{candidate['id']}", json={"action": "reject"}).raise_for_status()
        print("  rejeitado\n")
    else:
        print("  saltado\n")


if __name__ == "__main__":
    main()
