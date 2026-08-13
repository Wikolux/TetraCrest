"""Product Decision Specialist structured outputs (Milestone 4) - domain
validation, mirroring test_discovery_outputs.py's own coverage exactly.
"""

import pytest

from app.services.ai.agents.specialists.product_management.shared.decision_record import DecisionFramework
from app.services.ai.agents.specialists.product_management.product_decision.outputs import (
    AlternativeComparison,
    ConfidenceAssessment,
    DecisionHistorySummary,
    DecisionReview,
    DecisionSummary,
    FrameworkAnalysis,
    OptionScore,
    PrioritizationResult,
    PrioritizedItem,
    ProductDecisionContext,
    RecommendationReport,
    RiskAssessment,
    RiskItem,
    TradeoffReport,
)


# --- ProductDecisionContext -------------------------------------------------------------------


def test_product_decision_context_requires_question():
    with pytest.raises(ValueError):
        ProductDecisionContext(question="")


def test_product_decision_context_coerces_list_fields_to_tuples():
    context = ProductDecisionContext(question="build vs buy?", options=["build", "buy"], criteria=["cost"])
    assert context.options == ("build", "buy")
    assert context.criteria == ("cost",)


# --- PrioritizedItem / PrioritizationResult ------------------------------------------------------


def test_prioritized_item_requires_name():
    with pytest.raises(ValueError):
        PrioritizedItem(name="")


def test_prioritization_result_coerces_items_to_tuple():
    result = PrioritizationResult(framework=DecisionFramework.RICE, items=[PrioritizedItem(name="A")])
    assert isinstance(result.items, tuple)


# --- FrameworkAnalysis --------------------------------------------------------------------------


def test_framework_analysis_requires_approach_notes():
    with pytest.raises(ValueError):
        FrameworkAnalysis(framework=DecisionFramework.ICE, approach_notes="")


def test_framework_analysis_defaults():
    analysis = FrameworkAnalysis(framework=DecisionFramework.RICE, approach_notes="applying RICE")
    assert analysis.score is None
    assert analysis.category == ""


# --- TradeoffReport ------------------------------------------------------------------------------


def test_tradeoff_report_requires_non_empty_tradeoffs():
    with pytest.raises(ValueError):
        TradeoffReport(tradeoffs=())


def test_tradeoff_report_coerces_list_to_tuple():
    report = TradeoffReport(tradeoffs=["speed vs cost"])
    assert report.tradeoffs == ("speed vs cost",)


# --- RiskItem / RiskAssessment ---------------------------------------------------------------------


def test_risk_item_requires_description():
    with pytest.raises(ValueError):
        RiskItem(description="")


def test_risk_assessment_requires_non_empty_risks():
    with pytest.raises(ValueError):
        RiskAssessment(risks=())


# --- ConfidenceAssessment --------------------------------------------------------------------------


def test_confidence_assessment_requires_valid_range():
    with pytest.raises(ValueError):
        ConfidenceAssessment(confidence=1.5, rationale="x", remaining_uncertainty="y")
    with pytest.raises(ValueError):
        ConfidenceAssessment(confidence=-0.1, rationale="x", remaining_uncertainty="y")


def test_confidence_assessment_requires_rationale():
    with pytest.raises(ValueError):
        ConfidenceAssessment(confidence=0.5, rationale="", remaining_uncertainty="y")


def test_confidence_assessment_requires_remaining_uncertainty():
    with pytest.raises(ValueError):
        ConfidenceAssessment(confidence=0.5, rationale="x", remaining_uncertainty="")


def test_confidence_assessment_accepts_valid_values():
    assessment = ConfidenceAssessment(confidence=0.7, rationale="strong evidence", remaining_uncertainty="low")
    assert assessment.confidence == 0.7


# --- RecommendationReport - the core "never fabricate certainty" enforcement -----------------------


def _report(**overrides):
    defaults = dict(
        recommendation="Proceed",
        framework=DecisionFramework.RICE,
        assumptions=("market stable",),
        risks=("adoption may lag",),
        tradeoffs=("speed vs polish",),
        expected_impact="moderate uplift expected",
        confidence=0.6,
        remaining_uncertainty="moderate",
        evidence_ids=("1", "2"),
    )
    defaults.update(overrides)
    return RecommendationReport(**defaults)


def test_recommendation_report_requires_text():
    with pytest.raises(ValueError):
        _report(recommendation="")


def test_recommendation_report_requires_assumptions():
    with pytest.raises(ValueError):
        _report(assumptions=())


def test_recommendation_report_requires_risks():
    with pytest.raises(ValueError):
        _report(risks=())


def test_recommendation_report_requires_tradeoffs():
    with pytest.raises(ValueError):
        _report(tradeoffs=())


def test_recommendation_report_requires_expected_impact():
    with pytest.raises(ValueError):
        _report(expected_impact="")


def test_recommendation_report_requires_valid_confidence_range():
    with pytest.raises(ValueError):
        _report(confidence=1.1)


def test_recommendation_report_requires_remaining_uncertainty():
    with pytest.raises(ValueError):
        _report(remaining_uncertainty="")


def test_recommendation_report_requires_evidence_or_explicit_gap():
    with pytest.raises(ValueError):
        _report(evidence_ids=(), evidence_gap="")


def test_recommendation_report_accepts_evidence_gap_alone():
    report = _report(evidence_ids=(), evidence_gap="no prior findings")
    assert report.evidence_ids == ()
    assert report.evidence_gap == "no prior findings"


def test_recommendation_report_valid_construction_succeeds():
    report = _report()
    assert report.recommendation == "Proceed"
    assert report.evidence_ids == ("1", "2")


# --- OptionScore / AlternativeComparison -------------------------------------------------------------


def test_option_score_requires_name():
    with pytest.raises(ValueError):
        OptionScore(name="")


def test_alternative_comparison_requires_at_least_two_options():
    with pytest.raises(ValueError):
        AlternativeComparison(options=(OptionScore(name="only-one"),))


def test_alternative_comparison_accepts_two_or_more():
    comparison = AlternativeComparison(options=(OptionScore(name="A"), OptionScore(name="B")))
    assert len(comparison.options) == 2


# --- DecisionSummary / DecisionReview / DecisionHistorySummary --------------------------------------


def test_decision_summary_requires_title_and_summary():
    with pytest.raises(ValueError):
        DecisionSummary(title="", framework="rice", summary="x")
    with pytest.raises(ValueError):
        DecisionSummary(title="x", framework="rice", summary="")


def test_decision_review_requires_title_and_review_notes():
    with pytest.raises(ValueError):
        DecisionReview(title="", original_outcome="", review_notes="notes")
    with pytest.raises(ValueError):
        DecisionReview(title="x", original_outcome="", review_notes="")


def test_decision_history_summary_requires_summary():
    with pytest.raises(ValueError):
        DecisionHistorySummary(summary="")


def test_decision_history_summary_coerces_frameworks_used_to_tuple():
    summary = DecisionHistorySummary(summary="3 decisions", frameworks_used=["rice", "ice"])
    assert summary.frameworks_used == ("rice", "ice")
