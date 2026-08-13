"""Insight, InsightType, InsightBasis, InsightPeriod - field defaults,
validation, tuple coercion, and to_memory_content() rendering. The most
important property this file protects: an Insight's rendered content
always carries its observation (and, when inferred, its conclusion kept
visibly separate) plus its supporting memory ids - the mechanism that
makes generated insights traceable rather than invented.
"""

import pytest

from app.services.ai.agents.specialists.personal_intelligence.shared.insight import (
    Insight,
    InsightBasis,
    InsightPeriod,
    InsightType,
)
from app.services.ai.agents.specialists.personal_intelligence.shared.types import MEMORY_TYPE_INSIGHT


def test_insight_type_has_all_seven_documented_members():
    assert {member.value for member in InsightType} == {
        "pattern",
        "habit",
        "contradiction",
        "alignment",
        "periodic_reflection",
        "recommendation",
        "profile_summary",
    }


def test_insight_basis_has_observed_and_inferred():
    assert {member.value for member in InsightBasis} == {"observed", "inferred"}


def test_insight_period_has_daily_weekly_monthly():
    assert {member.value for member in InsightPeriod} == {"daily", "weekly", "monthly"}


def test_insight_memory_type_is_personal_insight():
    assert Insight(insight_type=InsightType.PATTERN, title="x", observation="y").memory_type == MEMORY_TYPE_INSIGHT


def test_insight_defaults():
    insight = Insight(insight_type=InsightType.PATTERN, title="x", observation="y")
    assert insight.basis == InsightBasis.OBSERVED
    assert insight.conclusion == ""
    assert insight.supporting_memory_ids == ()
    assert insight.confidence == 1.0
    assert insight.subject == ""


def test_insight_coerces_a_list_of_supporting_memory_ids_to_a_tuple():
    insight = Insight(insight_type=InsightType.PATTERN, title="x", observation="y", supporting_memory_ids=[1, 2, 3])
    assert insight.supporting_memory_ids == (1, 2, 3)
    assert isinstance(insight.supporting_memory_ids, tuple)


@pytest.mark.parametrize("confidence", [-0.01, 1.01, 5.0])
def test_insight_rejects_out_of_bounds_confidence(confidence):
    with pytest.raises(ValueError, match="confidence"):
        Insight(insight_type=InsightType.PATTERN, title="x", observation="y", confidence=confidence)


@pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
def test_insight_accepts_boundary_confidence(confidence):
    assert Insight(insight_type=InsightType.PATTERN, title="x", observation="y", confidence=confidence).confidence == confidence


def test_inferred_insight_without_a_conclusion_is_rejected():
    with pytest.raises(ValueError, match="conclusion"):
        Insight(insight_type=InsightType.HABIT, title="x", observation="y", basis=InsightBasis.INFERRED)


def test_inferred_insight_with_a_conclusion_is_accepted():
    insight = Insight(
        insight_type=InsightType.HABIT, title="x", observation="y", basis=InsightBasis.INFERRED, conclusion="z"
    )
    assert insight.conclusion == "z"


def test_observed_insight_does_not_require_a_conclusion():
    insight = Insight(insight_type=InsightType.PATTERN, title="x", observation="y", basis=InsightBasis.OBSERVED)
    assert insight.conclusion == ""


def test_insight_is_frozen_and_hashable():
    insight = Insight(insight_type=InsightType.PATTERN, title="x", observation="y")
    with pytest.raises(AttributeError):
        insight.title = "mutated"
    hash(insight)  # must not raise


# --- to_memory_content(): the traceability contract ------------------------------------------


def test_observed_content_includes_type_title_and_observation():
    insight = Insight(insight_type=InsightType.PATTERN, title="Recurring theme: 'x'", observation="'x' appeared 3 times.")
    content = insight.to_memory_content()
    assert "pattern" in content
    assert "Recurring theme: 'x'" in content
    assert "Observed: 'x' appeared 3 times." in content


def test_observed_content_omits_an_inferred_clause():
    insight = Insight(insight_type=InsightType.PATTERN, title="x", observation="y", basis=InsightBasis.OBSERVED)
    assert "Inferred:" not in insight.to_memory_content()


def test_inferred_content_includes_both_observed_and_inferred_clauses():
    insight = Insight(
        insight_type=InsightType.HABIT,
        title="x",
        observation="observed fact",
        basis=InsightBasis.INFERRED,
        conclusion="inferred conclusion",
    )
    content = insight.to_memory_content()
    assert "Observed: observed fact" in content
    assert "Inferred: inferred conclusion" in content


def test_content_includes_supporting_memory_ids_when_present():
    insight = Insight(insight_type=InsightType.PATTERN, title="x", observation="y", supporting_memory_ids=(1, 2, 3))
    assert "Supporting memories: 1, 2, 3." in insight.to_memory_content()


def test_content_omits_supporting_memories_clause_when_empty():
    insight = Insight(insight_type=InsightType.PERIODIC_REFLECTION, title="x", observation="y")
    assert "Supporting memories" not in insight.to_memory_content()


def test_supporting_memory_ids_may_be_empty_for_an_honest_no_data_reflection():
    # a periodic reflection over an empty window legitimately observes
    # "nothing happened" - this must not raise.
    insight = Insight(
        insight_type=InsightType.PERIODIC_REFLECTION,
        title="Weekly reflection",
        observation="0 memories were recorded during this weekly window.",
        basis=InsightBasis.INFERRED,
        conclusion="Recurring themes this weekly: no strong recurring themes.",
        confidence=0.0,
    )
    assert insight.supporting_memory_ids == ()
