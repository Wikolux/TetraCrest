"""Strategy & Portfolio Specialist structured outputs (Milestone 6) -
domain validation, mirroring test_discovery_outputs.py's/
test_decision_outputs.py's/test_delivery_outputs.py's own coverage.
"""

import pytest

from app.services.ai.agents.specialists.product_management.shared.decision_record import DecisionFramework
from app.services.ai.agents.specialists.product_management.strategy_portfolio.outputs import (
    InitiativeSequence,
    OKRAssessment,
    OpportunityComparison,
    PortfolioAssessment,
    PrioritizedInitiative,
    ProductVisionAssessment,
    RoadmapEntry,
    RoadmapRecommendation,
    StrategyRecommendation,
    StrategySummary,
    TradeoffAssessment,
)


# --- RoadmapEntry / RoadmapRecommendation -------------------------------------------------------


def test_roadmap_entry_requires_title_and_horizon():
    with pytest.raises(ValueError):
        RoadmapEntry(title="", horizon="now")
    with pytest.raises(ValueError):
        RoadmapEntry(title="Ship X", horizon="")


def test_roadmap_recommendation_requires_non_empty_items():
    with pytest.raises(ValueError):
        RoadmapRecommendation(items=(), tradeoffs=("x",))


def test_roadmap_recommendation_requires_non_empty_tradeoffs():
    with pytest.raises(ValueError):
        RoadmapRecommendation(items=(RoadmapEntry(title="Ship X", horizon="now"),), tradeoffs=())


def test_roadmap_recommendation_coerces_lists_to_tuples():
    recommendation = RoadmapRecommendation(
        items=[RoadmapEntry(title="Ship X", horizon="now")], tradeoffs=["a vs b"], evidence_ids=["1"]
    )
    assert isinstance(recommendation.items, tuple)
    assert recommendation.tradeoffs == ("a vs b",)
    assert recommendation.evidence_ids == ("1",)


# --- PrioritizedInitiative / InitiativeSequence -------------------------------------------------


def test_prioritized_initiative_requires_name():
    with pytest.raises(ValueError):
        PrioritizedInitiative(name="")


def test_initiative_sequence_coerces_items_to_tuple():
    sequence = InitiativeSequence(framework=DecisionFramework.RICE, items=[PrioritizedInitiative(name="A")])
    assert isinstance(sequence.items, tuple)


# --- OpportunityComparison -----------------------------------------------------------------------


def test_opportunity_comparison_requires_at_least_two_options():
    with pytest.raises(ValueError):
        OpportunityComparison(options=("only-one",))


def test_opportunity_comparison_accepts_two_or_more():
    comparison = OpportunityComparison(options=("A", "B"))
    assert len(comparison.options) == 2


# --- ProductVisionAssessment ----------------------------------------------------------------------


def test_product_vision_assessment_requires_vision_statement():
    with pytest.raises(ValueError):
        ProductVisionAssessment(vision_statement="")


def test_product_vision_assessment_coerces_lists_to_tuples():
    assessment = ProductVisionAssessment(vision_statement="Be the simplest tool", aligned_initiatives=["A"], misaligned_initiatives=["B"])
    assert assessment.aligned_initiatives == ("A",)
    assert assessment.misaligned_initiatives == ("B",)


# --- OKRAssessment ---------------------------------------------------------------------------------


def test_okr_assessment_requires_objective():
    with pytest.raises(ValueError):
        OKRAssessment(objective="")


def test_okr_assessment_defaults():
    assessment = OKRAssessment(objective="Improve retention")
    assert assessment.key_results == ()
    assert assessment.north_star == ""


# --- TradeoffAssessment -----------------------------------------------------------------------------


def test_tradeoff_assessment_requires_non_empty_tradeoffs():
    with pytest.raises(ValueError):
        TradeoffAssessment(tradeoffs=())


# --- StrategyRecommendation - the core "never fabricate strategy" enforcement -----------------------


def _recommendation(**overrides):
    defaults = dict(
        recommendation="Proceed",
        assumptions=("market stable",),
        trade_offs=("speed vs polish",),
        risks=("adoption may lag",),
        confidence=0.6,
        remaining_uncertainty="moderate",
        evidence_ids=("1", "2"),
    )
    defaults.update(overrides)
    return StrategyRecommendation(**defaults)


def test_recommendation_requires_text():
    with pytest.raises(ValueError):
        _recommendation(recommendation="")


def test_recommendation_requires_assumptions():
    with pytest.raises(ValueError):
        _recommendation(assumptions=())


def test_recommendation_requires_trade_offs():
    with pytest.raises(ValueError):
        _recommendation(trade_offs=())


def test_recommendation_requires_risks():
    with pytest.raises(ValueError):
        _recommendation(risks=())


def test_recommendation_requires_valid_confidence_range():
    with pytest.raises(ValueError):
        _recommendation(confidence=1.1)


def test_recommendation_requires_remaining_uncertainty():
    with pytest.raises(ValueError):
        _recommendation(remaining_uncertainty="")


def test_recommendation_requires_evidence_or_explicit_gap():
    with pytest.raises(ValueError):
        _recommendation(evidence_ids=(), evidence_gap="")


def test_recommendation_accepts_evidence_gap_alone():
    recommendation = _recommendation(evidence_ids=(), evidence_gap="no prior findings")
    assert recommendation.evidence_gap == "no prior findings"


def test_recommendation_has_no_counterpoint_field():
    # Deliberate structural difference from Product Decision's own
    # RecommendationReport (Milestone 4) - Strategy & Portfolio does not
    # perform counterpoint-and-framework-application decision discipline
    # (Architecture §12/ARR's own non-responsibility boundary).
    recommendation = _recommendation()
    assert not hasattr(recommendation, "counterpoint")


def test_recommendation_valid_construction_succeeds():
    recommendation = _recommendation()
    assert recommendation.recommendation == "Proceed"


# --- PortfolioAssessment - the v1 scope-limitation enforcement -------------------------------------


def test_portfolio_assessment_requires_non_empty_products():
    with pytest.raises(ValueError):
        PortfolioAssessment(products=(), per_product_notes=(), scope_note="scoped")


def test_portfolio_assessment_requires_scope_note():
    with pytest.raises(ValueError, match="scope_note"):
        PortfolioAssessment(products=("A",), per_product_notes=("A: 0 items",), scope_note="")


def test_portfolio_assessment_coerces_lists_to_tuples():
    assessment = PortfolioAssessment(products=["A", "B"], per_product_notes=["A: 0", "B: 0"], scope_note="scoped")
    assert assessment.products == ("A", "B")
    assert assessment.per_product_notes == ("A: 0", "B: 0")


# --- StrategySummary -------------------------------------------------------------------------------


def test_strategy_summary_requires_summary():
    with pytest.raises(ValueError):
        StrategySummary(summary="")


def test_strategy_summary_defaults():
    summary = StrategySummary(summary="3 items")
    assert summary.roadmap_item_count == 0
    assert summary.metric_count == 0
