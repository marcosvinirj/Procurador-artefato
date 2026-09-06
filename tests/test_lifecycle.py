from core.lifecycle import decide


def test_um_dia_saturado_nao_arquiva():
    """Um snapshot ruidoso isolado nao pode arquivar nada — exige sequencia."""
    changes = decide(scores={"a": 20.0}, statuses={"a": "active"}, streaks={"a": 0})
    assert changes == [type(changes[0])("a", "active", 1)]


def test_sequencia_completa_arquiva():
    changes = decide(
        scores={"a": 20.0}, statuses={"a": "active"}, streaks={"a": 4}, threshold_days=5
    )
    assert changes[0].status == "archived"
    assert changes[0].low_score_streak == 0  # zera ao transitar


def test_recuperacao_zera_a_contagem():
    """Um dia bom no meio da sequencia recomeca a contagem do zero."""
    changes = decide(scores={"a": 70.0}, statuses={"a": "active"}, streaks={"a": 4})
    assert changes[0].status == "active"
    assert changes[0].low_score_streak == 0


def test_arquivado_reativa_apos_sequencia_boa():
    changes = decide(
        scores={"a": 70.0}, statuses={"a": "archived"}, streaks={"a": 4}, threshold_days=5
    )
    assert changes[0].status == "active"
    assert changes[0].low_score_streak == 0


def test_arquivado_que_continua_saturado_fica_parado():
    """Enquanto arquivado, continuar saturado nao gera mudanca nem escrita."""
    changes = decide(scores={"a": 20.0}, statuses={"a": "archived"}, streaks={"a": 0})
    assert changes == []


def test_pending_e_rejected_ficam_de_fora():
    changes = decide(
        scores={"a": 10.0, "b": 10.0},
        statuses={"a": "pending", "b": "rejected"},
        streaks={},
    )
    assert changes == []


def test_sem_mudanca_nao_gera_entrada():
    """Ativo e saudavel, sem streak: nada a escrever."""
    changes = decide(scores={"a": 80.0}, statuses={"a": "active"}, streaks={"a": 0})
    assert changes == []
