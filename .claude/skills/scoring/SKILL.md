---
name: scoring
description: Metodologia do score de oportunidade do TrendPrint — normalizacao modelo→keyword→sinonimos, gap procura/concorrencia, pesos e tratamento de sinais em falta. Usar sempre que se mexa em core/scoring.py, nos pesos, na normalizacao, ou ao interpretar/explicar um score.
---

# Score de oportunidade

Fonte de verdade do dominio. `core/scoring.py` implementa exatamente o que esta
aqui; qualquer alteracao muda os dois em conjunto.

## A pergunta que o score responde

Nao "o que esta a viralizar", mas **"o que tem procura de compra com o mercado
ainda aberto"**. Um modelo pode estar a explodir em atencao e pontuar baixo: se
ja ha 9000 listagens a vende-lo, a atencao ja foi capturada por outros.

## Normalizacao: modelo → keyword → sinonimos

Um modelo (`Polvo Articulado`) nao e um termo de mercado. O que se mede e a sua
**`keyword` canonica** (`articulated octopus`), o termo pelo qual o produto e
efetivamente procurado e vendido.

Os **`synonyms`** existem porque o mesmo produto vende sob varios nomes
(`fidget octopus`, `kraken toy`). Ignora-los subestima **as duas** pontas:
mede-se menos concorrencia do que existe e menos procura do que existe. Regra:

- **concorrencia**: o termo com **mais** listagens manda — e o piso real de
  saturacao do produto. Somar termos duplicaria listagens que aparecem em varias
  pesquisas;
- **procura**: usa-se o termo principal, para que a serie temporal seja compara-
  vel de dia para dia.

O numero de termos consultados esta limitado (`sources.MAX_TERMS`) pelo orcamento
de ~10s da funcao do cron, nao por design.

## Os passos

1. **Procura** — sinal de compra do ultimo dia (`demand_raw`). **Todas as
   fontes que alimentam este campo tem de devolver a mesma banda 0..100.**
   Nao e cosmetica: o campo e comparado por percentil dentro da categoria, e
   uma fonte que devolvesse outra unidade (ex: visualizacoes do YouTube, aos
   milhoes) poria os seus modelos no topo so pela magnitude, nao por merito —
   um numero errado, que e pior do que sinal nenhum. Ver
   `core/sources._views_to_band`.
2. **Direcao** — variacao vs. ~7 dias antes; sem historico, neutro (50).
   O crescimento e limitado a ±100%: acima disso e ruido de normalizacao da
   fonte, nao informacao de mercado.
3. **Concorrencia** — saturacao do mercado para a keyword (`competition_raw`).
4. **Margem** — estimativa (`margin_est`).
5. **Normalizacao** — `demand`, `competition` e `margin` viram 0..100 por
   **percentil dentro da categoria**. Por categoria porque as escalas nao se
   misturam: 300 listagens saturam um nicho de utilidades e nao sao nada em
   decoracao. O percentil usa a media dos ranks em empate, logo modelos
   identicos recebem exatamente o mesmo valor — e com N modelos os extremos sao
   `100·(N−0.5)/N` e `100·0.5/N`, nunca 100 e 0.
6. **Gap de oportunidade** — `demand_norm − competition_norm` (−100..100),
   remapeado para 0..100. E o coracao: procura alta **com** concorrencia baixa.
7. **Score final** — soma ponderada.

## Pesos

Em `WEIGHTS`, no topo de `core/scoring.py`:

| Componente | Peso | Porque |
|---|---|---|
| `gap` | 60% | e o unico que distingue mercado aberto de hype ja capturado |
| `trend` | 25% | evita premiar procura alta mas em queda |
| `margin` | 15% | desempata; sozinho nao decide nada |

O score **nunca e gravado** — calcula-se na leitura dos snapshots. Mudar os pesos
recalibra o historico todo sem migracao nem recolha nova.

## Sinais em falta

Um componente sem dados **nao conta como zero** — zero e um dado mau inventado.
O peso e **redistribuido proporcionalmente** pelos disponiveis, para que o score
continue na escala 0..100 e comparavel. Consequencia a assumir: um modelo com
menos sinais tem um score mais fragil, ainda que numericamente valido.

## Leitura dos limiares (frontend)

`>= 65` mercado aberto · `45–65` disputado · `< 45` saturado. Sao limiares de
apresentacao, definidos em `app/lib/score.ts`; nao entram no calculo.

## Ao alterar

1. Atualizar este ficheiro **e** `core/scoring.py` na mesma mudanca.
2. Cobrir com testes em `tests/test_scoring.py`: gap alto, gap negativo por
   saturacao, empate — os tres casos que nao podem falhar.
3. Nao introduzir dependencias em `scoring.py`: e stdlib puro de proposito, para
   ser testavel sem rede nem base de dados.
