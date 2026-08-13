"""Reflection & growth reasoning (§10): observed fact / inferred pattern
/ hypothesis / recommendation must remain structurally distinguishable -
never presented as the same kind of claim."""

import pytest

from app.services.personal_os.reasoning import GrowthRecommendation, Hypothesis, InferredPattern, ObservedFact
from app.services.personal_os.shared.types import ObservationBasis


def test_observed_fact_has_observed_fact_basis():
    fact = ObservedFact(statement="Task X was postponed on Monday")
    assert isinstance(fact, ObservedFact)


def test_inferred_pattern_requires_at_least_two_supporting_facts():
    one_fact = (ObservedFact(statement="A"),)
    with pytest.raises(ValueError):
        InferredPattern(statement="pattern", supporting_facts=one_fact)


def test_inferred_pattern_carries_inferred_pattern_basis():
    facts = (ObservedFact(statement="A"), ObservedFact(statement="B"))
    pattern = InferredPattern(statement="Three similar tasks were postponed this week", supporting_facts=facts)
    assert pattern.basis == ObservationBasis.INFERRED_PATTERN


def test_hypothesis_requires_the_pattern_it_explains():
    with pytest.raises(ValueError):
        Hypothesis(statement="Estimation problem, not motivation", explains=None)


def test_hypothesis_carries_hypothesis_basis_distinct_from_pattern():
    facts = (ObservedFact(statement="A"), ObservedFact(statement="B"))
    pattern = InferredPattern(statement="Repeated postponement", supporting_facts=facts)
    hypothesis = Hypothesis(statement="May indicate an estimation problem rather than a motivation problem", explains=pattern)
    assert hypothesis.basis == ObservationBasis.HYPOTHESIS
    assert hypothesis.basis != pattern.basis


def test_recommendation_requires_the_hypothesis_it_responds_to():
    with pytest.raises(ValueError):
        GrowthRecommendation(statement="Pad estimates by 50%", responds_to=None)


def test_all_four_reasoning_kinds_carry_distinct_basis_values():
    facts = (ObservedFact(statement="A"), ObservedFact(statement="B"))
    pattern = InferredPattern(statement="pattern", supporting_facts=facts)
    hypothesis = Hypothesis(statement="hypothesis", explains=pattern)
    recommendation = GrowthRecommendation(statement="recommendation", responds_to=hypothesis)

    bases = {pattern.basis, hypothesis.basis, recommendation.basis}
    assert bases == {ObservationBasis.INFERRED_PATTERN, ObservationBasis.HYPOTHESIS, ObservationBasis.RECOMMENDATION}
    assert len(bases) == 3  # never collapsed into one shared "basis"


def test_inference_is_never_presented_as_fact_the_worked_example():
    """Mirrors §10's own example: never "Victor is procrastinating" (a
    fact-shaped claim); always a pattern with named supporting facts, a
    hypothesis explicitly framed as a candidate explanation."""
    facts = (
        ObservedFact(statement="Task A: estimated 1h, took 3h, postponed once"),
        ObservedFact(statement="Task B: estimated 2h, took 5h, postponed once"),
        ObservedFact(statement="Task C: estimated 1h, took 4h, postponed twice"),
    )
    pattern = InferredPattern(statement="Three similar tasks were postponed this week", supporting_facts=facts)
    hypothesis = Hypothesis(
        statement="In each case the original estimate was less than the actual time required. "
        "This may indicate an estimation problem rather than a motivation problem.",
        explains=pattern,
    )
    assert "may indicate" in hypothesis.statement
    assert hypothesis.basis != ObservationBasis.OBSERVED_FACT
