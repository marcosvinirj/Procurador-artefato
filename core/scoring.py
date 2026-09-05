"""Score de oportunidade: procura alta + concorrencia baixa + margem saudavel.

Modulo puro (so stdlib): nao toca em rede nem em base de dados, para poder ser
testado isoladamente. A metodologia esta documentada em .claude/skills/scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable, Sequence

# Pesos configuraveis. O gap domina porque e ele que distingue "mercado aberto"
# de "hype ja saturado"; a direcao evita premiar procura em queda; a margem
# desempata. Alterar aqui recalibra tudo sem migracao (o score nunca e gravado).
WEIGHTS: dict[str, float] = {"gap": 0.60, "trend": 0.25, "margin": 0.15}

TREND_WINDOW_DAYS = 7
# Crescimento diario acima de +100% (ou queda de -100%) satura a escala: alem
# disto o sinal e ruido de normalizacao das fontes, nao informacao de mercado.
TREND_CLAMP = 1.0
NEUTRAL = 50.0


@dataclass(frozen=True)
class Snapshot:
    day: date
    demand_raw: float | None = None
    competition_raw: float | None = None
    margin_est: float | None = None


@dataclass(frozen=True)
class Model:
    id: str
    name: str
    category: str
    keyword: str
    synonyms: tuple[str, ...] = ()
    snapshots: tuple[Snapshot, ...] = ()


@dataclass(frozen=True)
class Scored:
    model: Model
    score: float
    demand_norm: float | None
    competition_norm: float | None
    components: dict[str, float] = field(default_factory=dict)
    contributions: dict[str, float] = field(default_factory=dict)
    latest: Snapshot | None = None


def percentile_rank(values: Sequence[float], value: float) -> float:
    """Posicao de `value` dentro de `values`, em 0..100.

    Usa a media dos ranks em caso de empate, para que modelos identicos recebam
    exatamente a mesma normalizacao.
    """
    if not values:
        return NEUTRAL
    below = sum(1 for v in values if v < value)
    equal = sum(1 for v in values if v == value)
    return 100.0 * (below + 0.5 * equal) / len(values)


def opportunity_gap(demand_norm: float, competition_norm: float) -> float:
    """demand - competition (-100..100) remapeado para 0..100."""
    return (demand_norm - competition_norm + 100.0) / 2.0


def trend_score(snapshots: Sequence[Snapshot], window: int = TREND_WINDOW_DAYS) -> float:
    """Direcao da procura: ultimo dia vs. ~`window` dias antes, em 0..100.

    Sem historico suficiente devolve o neutro, para nao penalizar modelos novos.
    """
    series = [s for s in sorted(snapshots, key=lambda s: s.day) if s.demand_raw is not None]
    if len(series) < 2:
        return NEUTRAL
    latest = series[-1]
    cutoff = latest.day - timedelta(days=window)
    earlier = [s for s in series[:-1] if s.day <= cutoff]
    prior = earlier[-1] if earlier else series[0]
    if prior.demand_raw is None or prior.demand_raw <= 0:
        return NEUTRAL
    growth = (latest.demand_raw - prior.demand_raw) / prior.demand_raw
    clamped = max(-TREND_CLAMP, min(TREND_CLAMP, growth))
    return (clamped / TREND_CLAMP + 1.0) * 50.0


def latest_snapshot(snapshots: Iterable[Snapshot]) -> Snapshot | None:
    ordered = sorted(snapshots, key=lambda s: s.day)
    return ordered[-1] if ordered else None


def _weighted(components: dict[str, float]) -> tuple[float, dict[str, float]]:
    """Soma ponderada sobre os componentes disponiveis.

    Um componente em falta (ex: margem por ligar) faz o seu peso ser
    redistribuido pelos restantes, em vez de contar como zero — assumir zero
    seria inventar um dado mau.
    """
    total_weight = sum(WEIGHTS[k] for k in components)
    if total_weight <= 0:
        return NEUTRAL, {}
    contributions = {k: WEIGHTS[k] * v / total_weight for k, v in components.items()}
    return sum(contributions.values()), contributions


def score_models(models: Sequence[Model]) -> list[Scored]:
    """Pontua e ordena por oportunidade (desc).

    A normalizacao e por percentil *dentro da categoria*: 300 listagens saturam
    um nicho de utilidades mas sao nada em decoracao, logo comparar entre
    categorias distorceria o gap.
    """
    latest = {m.id: latest_snapshot(m.snapshots) for m in models}

    def pool(category: str, attr: str) -> list[float]:
        return [
            getattr(s, attr)
            for m in models
            if m.category == category and (s := latest[m.id]) and getattr(s, attr) is not None
        ]

    scored: list[Scored] = []
    for model in models:
        snap = latest[model.id]
        demand = competition = None
        components: dict[str, float] = {}

        if snap and snap.demand_raw is not None:
            demand = percentile_rank(pool(model.category, "demand_raw"), snap.demand_raw)
        if snap and snap.competition_raw is not None:
            competition = percentile_rank(pool(model.category, "competition_raw"), snap.competition_raw)
        if demand is not None and competition is not None:
            components["gap"] = opportunity_gap(demand, competition)

        components["trend"] = trend_score(model.snapshots)

        if snap and snap.margin_est is not None:
            components["margin"] = percentile_rank(pool(model.category, "margin_est"), snap.margin_est)

        score, contributions = _weighted(components)
        scored.append(
            Scored(
                model=model,
                score=round(score, 1),
                demand_norm=demand,
                competition_norm=competition,
                components={k: round(v, 1) for k, v in components.items()},
                contributions={k: round(v, 1) for k, v in contributions.items()},
                latest=snap,
            )
        )

    scored.sort(key=lambda s: (-s.score, s.model.name))
    return scored
