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
8. **Descoberta nunca publica sozinha.** Um candidato entra como `pending` e so
   fica visivel em `/api/models` depois de aprovado em `/api/candidates`
   (ver secao "Ciclo de vida"). Evita o site encher-se de lixo sem controlo.

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

# Arquivar saturados / reativar recuperados
curl -H "Authorization: Bearer $CRON_SECRET" localhost:8000/api/lifecycle

# Propor candidatos novos (Google Trends, a partir dos modelos ativos)
curl -H "Authorization: Bearer $CRON_SECRET" localhost:8000/api/discover

# Rever candidatos pendentes (aprovar/rejeitar), interativo, so local
TRENDPRINT_URL=http://localhost:8000 CRON_SECRET=... python scripts/review_candidates.py
```

## Configuracao manual (uma vez, no painel)

1. **Supabase** → SQL Editor → correr `supabase/schema.sql` (tabelas + seed + RLS).
   Ficheiro idempotente: correr outra vez depois de uma alteracao (ex: as
   colunas `status`/`source`/`low_score_streak`) so acrescenta o que falta.
2. **Vercel** → Settings → Environment Variables: `SUPABASE_URL`,
   `SUPABASE_SERVICE_KEY`, `CRON_SECRET` e, opcionalmente, `ETSY_API_KEY`, o
   par `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET`, e `YOUTUBE_API_KEY`.
   Sem `CRON_SECRET` definido, a Vercel nao assina as chamadas do cron e
   `/api/collect` responde 401 — que e o comportamento correto.
3. Tres crons em `vercel.json`, sempre UTC: `/api/collect` as 3h,
   `/api/lifecycle` as 4h, `/api/discover` as 5h. No plano Hobby cada um corre
   **uma vez por dia**, com ~10s de timeout — por isso os conectores do collect
   vao em paralelo (I/O puro) e o discover processa uma fatia pequena de
   sementes por vez; se o orcamento esgotar, `next_offset` retoma sem perder
   nada. O upsert e idempotente: repetir uma fatia nao duplica. (Se a conta nao
   aceitar tres crons no Hobby, os que faltarem podem ser disparados a mao, com
   a mesma cadencia, via curl ou um cron externo tipo cron-job.org apontado a
   rota, com o `CRON_SECRET`.)

## Ciclo de vida de um modelo

`models.status`: `active` (visivel, tracked) → `pending` (descoberto, a espera
de revisao) → `active` ou `rejected` (decisao humana) → `active` pode virar
`archived` sozinho se saturar (`core/lifecycle.py`) e voltar a `active` sozinho
se recuperar. Nunca se apaga uma linha: `archived` so deixa de aparecer no
ranking publico, o historico fica intacto e o link direto ainda abre.

A regra de arquivamento e sequencial, nao de um dia isolado: precisa de 5 dias
**seguidos** saturado (score < 45) para arquivar, e 5 dias seguidos recuperado
para reativar — um unico dia ruidoso (a Etsy falhou, o Trends bloqueou) nao
pode arquivar nada sozinho. Corre no seu proprio cron (`/api/lifecycle`, 4h
UTC), nao pendurado na recolha: quando ia no fim do `/api/collect`, so corria
se a recolha tivesse terminado a lista toda — e com a lista a crescer isso
deixou de acontecer (40 de 42 dentro do orcamento => arquivamento saltado
todos os dias). Separado, tem os seus ~10s e nao depende disso.

## Onde mexer

| Quero… | Ficheiro |
|---|---|
| mudar pesos ou a formula | `core/scoring.py` + `.claude/skills/scoring/SKILL.md` |
| adicionar uma fonte de dados (sinal de um modelo existente) | `.claude/agents/data-source.md` (subagente) |
| adicionar uma fonte de descoberta (candidatos novos) | `core/discovery.py` |
| mudar a regra de arquivamento (dias, limiar) | `core/lifecycle.py` — `DEFAULT_THRESHOLD_DAYS`, `SATURATED_THRESHOLD` em `core/scoring.py` |
| adicionar uma rota | `api/index.py` — um so `FastAPI()` |
| mexer no visual | `app/components/` |

## Estado das fontes

| Sinal | Fonte | Estado |
|---|---|---|
| concorrencia + margem | Etsy API v3 (`listings/active`) | real, exige `ETSY_API_KEY` |
| concorrencia + margem (fallback) | eBay Browse API (`item_summary/search`) | real, exige `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` |
| direcao da procura | Google Trends (endpoint publico) | real, sem chave, pode ser bloqueado |
| direcao da procura (fallback) | YouTube Data API v3 (visualizacoes) | real, exige `YOUTUBE_API_KEY`, quota gratuita 10k/dia |
| procura de compra | ritmo de reviews no topo | **stub** — `review_velocity` devolve `None` |
