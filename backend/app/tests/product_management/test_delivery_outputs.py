"""Delivery Specialist structured outputs (Milestone 5) - domain
validation, mirroring test_discovery_outputs.py/test_decision_outputs.py's
own coverage exactly.
"""

import pytest

from app.services.ai.agents.specialists.product_management.delivery.outputs import (
    ConfidenceFactor,
    DependencyItem,
    DependencyMap,
    DeliveryConfidenceScore,
    DeliveryRecommendation,
    DeliveryRiskItem,
    DeliveryRiskReport,
    EpicPlan,
    RetrospectiveSummary,
    SprintPlan,
    SprintSummary,
    StoryBreakdown,
)


# --- ConfidenceFactor / DeliveryConfidenceScore ------------------------------------------------


def test_confidence_factor_requires_label():
    with pytest.raises(ValueError):
        ConfidenceFactor(label="", satisfied=True)


def test_confidence_score_requires_percent_in_range():
    with pytest.raises(ValueError):
        DeliveryConfidenceScore(score_percent=101, factors=(ConfidenceFactor("x", True),))
    with pytest.raises(ValueError):
        DeliveryConfidenceScore(score_percent=-1, factors=(ConfidenceFactor("x", True),))


def test_confidence_score_requires_non_empty_factors():
    with pytest.raises(ValueError):
        DeliveryConfidenceScore(score_percent=50, factors=())


def test_confidence_score_supporting_and_missing_properties():
    score = DeliveryConfidenceScore(
        score_percent=50,
        factors=(ConfidenceFactor("A", True), ConfidenceFactor("B", False, "missing B")),
    )
    assert [f.label for f in score.supporting] == ["A"]
    assert [f.label for f in score.missing] == ["B"]


# --- SprintPlan ----------------------------------------------------------------------------------


def test_sprint_plan_requires_sprint_goal():
    with pytest.raises(ValueError):
        SprintPlan(sprint_goal="")


def test_sprint_plan_coerces_list_fields_to_tuples():
    plan = SprintPlan(sprint_goal="Ship X", items=["a", "b"], evidence_ids=["1"])
    assert plan.items == ("a", "b")
    assert plan.evidence_ids == ("1",)


# --- StoryBreakdown / EpicPlan ---------------------------------------------------------------------


def test_story_breakdown_requires_parent():
    with pytest.raises(ValueError):
        StoryBreakdown(parent="", stories=("a",))


def test_story_breakdown_requires_non_empty_stories():
    with pytest.raises(ValueError):
        StoryBreakdown(parent="Spec", stories=())


def test_epic_plan_requires_epic_title():
    with pytest.raises(ValueError):
        EpicPlan(epic_title="")


def test_epic_plan_defaults_to_empty_stories():
    plan = EpicPlan(epic_title="Epic A")
    assert plan.stories == ()


# --- DependencyItem / DependencyMap -----------------------------------------------------------------


def test_dependency_item_requires_name():
    with pytest.raises(ValueError):
        DependencyItem(name="")


def test_dependency_map_requires_non_empty_dependencies():
    with pytest.raises(ValueError):
        DependencyMap(dependencies=())


# --- DeliveryRiskItem / DeliveryRiskReport -----------------------------------------------------------


def test_risk_item_requires_description():
    with pytest.raises(ValueError):
        DeliveryRiskItem(description="")


def test_risk_report_requires_non_empty_risks():
    with pytest.raises(ValueError):
        DeliveryRiskReport(risks=())


# --- DeliveryRecommendation - the core "no fabrication" enforcement ------------------------------


def _recommendation(**overrides):
    defaults = dict(
        recommendation="Proceed",
        confidence=DeliveryConfidenceScore(score_percent=75, factors=(ConfidenceFactor("A", True),)),
        evidence_ids=("1", "2"),
    )
    defaults.update(overrides)
    return DeliveryRecommendation(**defaults)


def test_recommendation_requires_text():
    with pytest.raises(ValueError):
        _recommendation(recommendation="")


def test_recommendation_requires_evidence_or_explicit_gap():
    with pytest.raises(ValueError):
        _recommendation(evidence_ids=(), evidence_gap="")


def test_recommendation_accepts_evidence_gap_alone():
    recommendation = _recommendation(evidence_ids=(), evidence_gap="no prior findings")
    assert recommendation.evidence_ids == ()
    assert recommendation.evidence_gap == "no prior findings"


def test_recommendation_valid_construction_succeeds():
    recommendation = _recommendation()
    assert recommendation.recommendation == "Proceed"
    assert recommendation.confidence.score_percent == 75


# --- SprintSummary / RetrospectiveSummary -------------------------------------------------------------


def test_sprint_summary_defaults():
    summary = SprintSummary(summary="3 artifacts")
    assert summary.artifact_count == 0
    assert summary.feature_count == 0


def test_retrospective_summary_requires_summary():
    with pytest.raises(ValueError):
        RetrospectiveSummary(summary="")


def test_retrospective_summary_coerces_list_fields_to_tuples():
    summary = RetrospectiveSummary(summary="1 of 2 delivered", planned=["a", "b"], actual=["a"], gaps=["b"], surprises=[])
    assert summary.planned == ("a", "b")
    assert summary.actual == ("a",)
    assert summary.gaps == ("b",)
    assert summary.surprises == ()
