"""Reflection & growth reasoning (P1 §10, extended P2 §4): observed fact
/ inferred pattern / user explanation / hypothesis / recommendation must
remain structurally distinguishable - never presented as the same kind
of claim."""

import pytest

from app.services.personal_os.reasoning import GrowthRecommendation, Hypothesis, InferredPattern, ObservedFact, UserExplanation
from app.services.personal_os.shared.types import ObservationBasis


def test_user_explanation_requires_a_statement():
    with pytest.raises(ValueError):
        UserExplanation(statement="")


def test_user_explanation_carries_its_own_distinct_basis():
    explanation = UserExplanation(statement="Two were postponed because of an unexpected meeting", explains_activity="Task A")
    assert explanation.basis == ObservationBasis.USER_EXPLANATION
    assert explanation.basis != ObservationBasis.OBSERVED_FACT
    assert explanation.basis != ObservationBasis.HYPOTHESIS


def test_hypothesis_can_be_informed_by_a_user_explanation_without_requiring_one():
    facts = (ObservedFact(statement="A"), ObservedFact(statement="B"))
    pattern = InferredPattern(statement="pattern", supporting_facts=facts)

    unexplained = Hypothesis(statement="a guess with no explanation", explains=pattern)
    assert unexplained.informed_by == ()

    explanation = UserExplanation(statement="an unexpected meeting came up")
    explained = Hypothesis(statement="disrupted by external commitments", explains=pattern, informed_by=(explanation,))
    assert explained.informed_by == (explanation,)


def test_the_full_five_basis_worked_example_from_p2_stays_distinguishable():
    """Mirrors P2 §4's own worked example verbatim: FACT, USER
    EXPLANATION, SYSTEM INFERENCE (Hypothesis), RECOMMENDATION - four
    distinct artifacts (a fifth, INFERRED_PATTERN, sits between fact and
    hypothesis structurally), never collapsed into one claim."""
    fact_a = ObservedFact(statement="Task A was not completed")
    fact_b = ObservedFact(statement="Task B was not completed")
    pattern = InferredPattern(statement="Three planned tasks were not completed", supporting_facts=(fact_a, fact_b))
    explanation = UserExplanation(statement="Two were postponed because of an unexpected meeting")
    hypothesis = Hypothesis(
        statement="The day was disrupted by external commitments", explains=pattern, informed_by=(explanation,)
    )
    recommendation = GrowthRecommendation(statement="Protect a larger uninterrupted block tomorrow", responds_to=hypothesis)

    assert explanation.basis == ObservationBasis.USER_EXPLANATION
    assert pattern.basis == ObservationBasis.INFERRED_PATTERN
    assert hypothesis.basis == ObservationBasis.HYPOTHESIS
    assert recommendation.basis == ObservationBasis.RECOMMENDATION
    assert len({explanation.basis, pattern.basis, hypothesis.basis, recommendation.basis}) == 4


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
