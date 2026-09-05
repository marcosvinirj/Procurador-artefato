from datetime import date, timedelta

from core.scoring import (
    Model,
    Snapshot,
    WEIGHTS,
    opportunity_gap,
    percentile_rank,
    score_models,
    trend_score,
)

TODAY = date(2026, 9, 5)


def series(demand: list[float], competition: float, margin: float | None = None) -> tuple[Snapshot, ...]:
    """Serie diaria a terminar em TODAY, com concorrencia/margem constantes."""
    start = TODAY - timedelta(days=len(demand) - 1)
    return tuple(
        Snapshot(start + timedelta(days=i), d, competition, margin) for i, d in enumerate(demand)
    )


def model(mid: str, demand: list[float], competition: float, margin: float | None = None) -> Model:
    return Model(mid, mid, "toys", mid, (), series(demand, competition, margin))


def test_gap_alto_vence_gap_negativo():
    """Procura no topo com concorrencia no fundo tem de bater o inverso."""
    aberto = model("aberto", [50.0] * 8, 10.0)
    saturado = model("saturado", [10.0] * 8, 900.0)
    ranked = score_models([saturado, aberto])

    assert [s.model.id for s in ranked] == ["aberto", "saturado"]
    # percentil de mid-rank: com 2 modelos os extremos sao 75/25, nao 100/0
    assert ranked[0].components["gap"] == 75.0
    assert ranked[1].components["gap"] == 25.0


def test_saturacao_derruba_modelo_a_bombar():
    """Atencao a explodir nao salva um mercado saturado: o gap manda."""
    # procura identica hoje: o que os separa e a concorrencia e a direcao
    hype = model("hype", [50.0] * 7 + [100.0], 900.0)
    calmo = model("calmo", [100.0] * 8, 5.0)
    ranked = score_models([hype, calmo])

    assert ranked[0].model.id == "calmo"
    assert ranked[0].components["gap"] > ranked[1].components["gap"]
    # o hype ganha a direcao por completo, mas os 25% nao viram os 60% do gap
    assert ranked[1].components["trend"] == 100.0
    assert ranked[0].components["trend"] == 50.0


def test_empate_produz_score_identico():
    a = model("a", [40.0] * 8, 100.0)
    b = model("b", [40.0] * 8, 100.0)
    ranked = score_models([a, b])

    assert ranked[0].score == ranked[1].score
    assert ranked[0].components["gap"] == 50.0  # empate = mediana de ambos os lados


def test_percentil_e_gap():
    assert percentile_rank([], 5.0) == 50.0
    assert percentile_rank([1.0, 2.0, 3.0], 3.0) > percentile_rank([1.0, 2.0, 3.0], 1.0)
    assert percentile_rank([5.0, 5.0], 5.0) == 50.0
    assert opportunity_gap(100.0, 0.0) == 100.0
    assert opportunity_gap(0.0, 100.0) == 0.0


def test_trend_neutro_sem_historico():
    assert trend_score(()) == 50.0
    assert trend_score((Snapshot(TODAY, 10.0),)) == 50.0
    assert trend_score(series([50.0] * 8, 1.0)) == 50.0
    assert trend_score(series([10.0] + [0.0] * 6 + [30.0], 1.0)) == 100.0  # clamp em +100%


def test_margem_em_falta_redistribui_peso():
    """Sem margem, o score sai da mesma escala 0..100 (peso redistribuido)."""
    ranked = score_models([model("a", [50.0] * 8, 10.0), model("b", [20.0] * 8, 400.0)])
    sem_margem = ranked[0]
    partes = sem_margem.components

    assert "margin" not in partes
    esperado = (WEIGHTS["gap"] * partes["gap"] + WEIGHTS["trend"] * partes["trend"]) / (
        WEIGHTS["gap"] + WEIGHTS["trend"]
    )
    assert abs(sem_margem.score - esperado) < 0.1
    assert abs(sum(sem_margem.contributions.values()) - sem_margem.score) < 0.2


def test_normaliza_dentro_da_categoria():
    """300 listagens saturam utilidades mas nao decoracao: as escalas nao se misturam."""
    util = Model("u", "u", "utilidades", "u", (), series([50.0] * 8, 300.0))
    deco_a = Model("da", "da", "decoracao", "da", (), series([50.0] * 8, 300.0))
    deco_b = Model("db", "db", "decoracao", "db", (), series([50.0] * 8, 9000.0))
    by_id = {s.model.id: s for s in score_models([util, deco_a, deco_b])}

    assert by_id["u"].competition_norm == 50.0  # unico da sua categoria
    assert by_id["da"].competition_norm == 25.0
    assert by_id["db"].competition_norm == 75.0


def test_modelo_sem_snapshots_nao_rebenta():
    vazio = Model("v", "v", "toys", "v", (), ())
    ranked = score_models([vazio, model("ok", [50.0] * 8, 10.0)])

    assert ranked[-1].model.id == "v"
    assert ranked[-1].score == 50.0  # so a direcao neutra sobrevive
