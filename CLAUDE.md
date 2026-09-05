# TrendPrint

Painel que diz a vendedores de prints 3D **o que imprimir para vender**: procura de
compra alta com o mercado ainda por fechar. Nao mede viralidade — mede oportunidade.

## Stack

- **Python e o nucleo.** Toda a logica de dados, score e API vive em `core/` e `api/`.
- FastAPI numa unica funcao (`api/index.py`), no runtime Python da Vercel.
- Next.js (App Router) + Tailwind na raiz (`app/`), sem bibliotecas de componentes.
- Supabase (Postgres) acedido so do servidor, com a service key.
- Vercel Cron dispara a recolha diaria.

## Invariantes

1. **Python e o nucleo.** Nada de reimplementar score ou acesso a dados no frontend.
2. **O frontend so fala com a nossa API.** Nunca com o Supabase diretamente.
3. **Segredos nunca chegam ao browser.** Sem `NEXT_PUBLIC_*` para chaves. A service
   key ignora RLS: se vazar, e acesso total a base de dados.
4. **`/api/collect` e protegida por `CRON_SECRET`**, comparado com `hmac.compare_digest`.
5. **Sem dados inventados.** Um conector que falha devolve `None`; o peso desse
   componente e redistribuido pelos restantes (`core/scoring._weighted`).
6. **O score nao se grava.** Calcula-se na leitura, para recalibrar sem migracao.
7. **Minimo de linhas.** A solucao mais pequena que esta correta ganha.

## Comandos

```bash
# Backend (terminal 1)
pip install -r requirements-dev.txt
uvicorn api.index:app --reload --port 8000

# Frontend (terminal 2) — em dev faz proxy de /api/* para o :8000
npm install && npm run dev          # http://localhost:3000

npm run build && npm run typecheck  # tem de passar sem warnings
python -m pytest tests -q           # testes do scoring

# Disparar a recolha a mao
curl -H "Authorization: Bearer $CRON_SECRET" localhost:8000/api/collect
```

## Configuracao manual (uma vez, no painel)

1. **Supabase** → SQL Editor → correr `supabase/schema.sql` (tabelas + seed + RLS).
2. **Vercel** → Settings → Environment Variables: `SUPABASE_URL`,
   `SUPABASE_SERVICE_KEY`, `CRON_SECRET` e, opcionalmente, `ETSY_API_KEY`.
   Sem `CRON_SECRET` definido, a Vercel nao assina as chamadas do cron e
   `/api/collect` responde 401 — que e o comportamento correto.
3. O cron (`0 3 * * *`, sempre UTC) vem de `vercel.json`. No plano Hobby corre
   **uma vez por dia**, com ~10s de timeout — a unica execucao diaria tem de
   cobrir o seed todo. Por isso os conectores correm em paralelo (I/O puro) e,
   se o orcamento esgotar, a resposta traz `next_offset` para retomar sem perder
   modelos. O upsert e idempotente: repetir uma fatia nao duplica nada.

## Onde mexer

| Quero… | Ficheiro |
|---|---|
| mudar pesos ou a formula | `core/scoring.py` + `.claude/skills/scoring/SKILL.md` |
| adicionar uma fonte de dados | `.claude/agents/data-source.md` (subagente) |
| adicionar uma rota | `api/index.py` — um so `FastAPI()` |
| mexer no visual | `app/components/` |

## Estado das fontes

| Sinal | Fonte | Estado |
|---|---|---|
| concorrencia + margem | Etsy API v3 (`listings/active`) | real, exige `ETSY_API_KEY` |
| direcao da procura | Google Trends (endpoint publico) | real, sem chave, pode ser bloqueado |
| procura de compra | ritmo de reviews no topo | **stub** — `review_velocity` devolve `None` |
