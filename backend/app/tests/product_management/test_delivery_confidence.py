"""build_confidence_score() - deterministic, explanatory scoring, never a
fabricated or probabilistic number.
"""

from app.services.ai.agents.specialists.product_management.delivery.confidence import build_confidence_score
from app.services.ai.agents.specialists.product_management.delivery.outputs import ConfidenceFactor


def test_all_factors_satisfied_scores_100():
    score = build_confidence_score(
        (ConfidenceFactor("A", True), ConfidenceFactor("B", True), ConfidenceFactor("C", True), ConfidenceFactor("D", True))
    )
    assert score.score_percent == 100
    assert score.missing == ()


def test_no_factors_satisfied_scores_0():
    score = build_confidence_score((ConfidenceFactor("A", False), ConfidenceFactor("B", False)))
    assert score.score_percent == 0
    assert score.supporting == ()


def test_partial_satisfaction_computes_exact_fraction():
    score = build_confidence_score(
        (ConfidenceFactor("A", True), ConfidenceFactor("B", True), ConfidenceFactor("C", False), ConfidenceFactor("D", False))
    )
    assert score.score_percent == 50


def test_the_task_own_worked_example_91_percent_is_not_literally_required_but_rounding_is_exact():
    # 3 of 4 satisfied = 75%, not a guessed or model-generated number.
    score = build_confidence_score(
        (ConfidenceFactor("A", True), ConfidenceFactor("B", True), ConfidenceFactor("C", True), ConfidenceFactor("D", False))
    )
    assert score.score_percent == 75
    assert [f.label for f in score.missing] == ["D"]


def test_score_explains_itself_via_supporting_and_missing():
    score = build_confidence_score(
        (
            ConfidenceFactor("Discovery validated", True),
            ConfidenceFactor("Decision approved", True),
            ConfidenceFactor("Dependencies mapped", True),
            ConfidenceFactor("Acceptance criteria complete", False, "No acceptance criteria supplied"),
        )
    )
    assert {f.label for f in score.supporting} == {"Discovery validated", "Decision approved", "Dependencies mapped"}
    assert {f.label for f in score.missing} == {"Acceptance criteria complete"}
