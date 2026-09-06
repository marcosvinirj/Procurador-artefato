"""Politica de arquivamento automatico dos modelos 'active'.

Um modelo saturado (score < SATURATED_THRESHOLD) por dias SEGUIDOS deixa de
aparecer no ranking publico — arquiva-se, nao se apaga: o historico fica
intacto, e ele reativa-se sozinho se o mercado reabrir. Um unico dia ruidoso
(a Etsy ja falhou, o Trends ja bloqueou) nao pode arquivar nada sozinho —
por isso a exigencia e de sequencia, nao de um snapshot isolado.

Modulo puro, como scoring.py: recebe estado e decide, nao escreve na base de
dados (isso fica em api/index.py, que chama core.db.update_model).
"""

from __future__ import annotations

from dataclasses import dataclass

from core.scoring import SATURATED_THRESHOLD

DEFAULT_THRESHOLD_DAYS = 5


@dataclass(frozen=True)
class LifecycleChange:
    model_id: str
    status: str
    low_score_streak: int


def decide(
    scores: dict[str, float],
    statuses: dict[str, str],
    streaks: dict[str, int],
    threshold_days: int = DEFAULT_THRESHOLD_DAYS,
) -> list[LifecycleChange]:
    """Uma entrada por modelo 'active' ou 'archived' presente em `scores`.

    'pending' e 'rejected' ficam de fora — a politica so se aplica a quem ja
    esteve, ou esta, no ar. A contagem e simetrica: dias saturados seguidos
    arquivam, dias recuperados seguidos reativam; um dia na direcao contraria
    zera a contagem (e "seguidos", nao "a maioria").
    """
    changes: list[LifecycleChange] = []
    for model_id, score in scores.items():
        status = statuses.get(model_id)
        if status not in ("active", "archived"):
            continue
        streak = streaks.get(model_id, 0)
        saturated = score < SATURATED_THRESHOLD

        moving_away = (status == "active" and saturated) or (status == "archived" and not saturated)
        new_streak = streak + 1 if moving_away else 0
        new_status = status
        if moving_away and new_streak >= threshold_days:
            new_status = "archived" if status == "active" else "active"
            new_streak = 0

        if new_status != status or new_streak != streak:
            changes.append(LifecycleChange(model_id, new_status, new_streak))
    return changes
