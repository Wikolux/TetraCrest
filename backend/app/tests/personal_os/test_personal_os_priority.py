"""Priority Intelligence (P5 §7-§10): candidate creation, factor
calculation, contextual (never permanently ranked) ordering, deadlines,
urgency, financial/strategic/opportunity/growth value, current intent,
consequence of delay, available time, day-mode influence, deterministic
ranking, and explanation data."""

from datetime import date

import pytest

from app.services.personal_os.day_mode import DayMode
from app.services.personal_os.priority import (
    CandidateItem,
    PriorityConfig,
    apply_override,
    calculate_score,
    explain,
    rank_candidates,
)
from app.services.personal_os.shared.types import DayModeKind, LifeDomain, PriorityFactor

TODAY = date(2026, 8, 13)
_CONFIG = PriorityConfig()


def _item(item_id="A", **kwargs):
    kwargs.setdefault("description", f"Item {item_id}")
    return CandidateItem(item_id=item_id, **kwargs)


# --- candidate creation -----------------------------------------------------------------------


def test_candidate_requires_a_description():
    with pytest.raises(ValueError):
        CandidateItem(item_id="A", description="")


@pytest.mark.parametrize("field_name", ["financial_value", "strategic_value", "opportunity_value", "growth_value", "momentum", "consequence_of_delay"])
def test_candidate_factor_values_must_be_within_zero_and_one(field_name):
    with pytest.raises(ValueError):
        CandidateItem(item_id="A", description="x", **{field_name: 1.5})


# --- factor calculation ------------------------------------------------------------------------


def test_urgency_is_highest_for_overdue_or_today_deadlines():
    score = calculate_score(_item(deadline=TODAY), today=TODAY, available_hours=8, day_mode=None)
    assert score.factor_values[PriorityFactor.URGENCY] == 1.0


def test_urgency_decreases_as_deadline_moves_further_out():
    near = calculate_score(_item(deadline=date(2026, 8, 15)), today=TODAY, available_hours=8, day_mode=None)
    far = calculate_score(_item(deadline=date(2026, 9, 1)), today=TODAY, available_hours=8, day_mode=None)
    assert near.factor_values[PriorityFactor.URGENCY] > far.factor_values[PriorityFactor.URGENCY]


def test_no_deadline_means_zero_urgency_and_zero_deadline_factor():
    score = calculate_score(_item(deadline=None), today=TODAY, available_hours=8, day_mode=None)
    assert score.factor_values[PriorityFactor.URGENCY] == 0.0
    assert score.factor_values[PriorityFactor.DEADLINE] == 0.0


def test_financial_value_passes_through_from_the_candidate():
    score = calculate_score(_item(financial_value=0.8), today=TODAY, available_hours=8, day_mode=None)
    assert score.factor_values[PriorityFactor.FINANCIAL_VALUE] == 0.8


def test_strategic_value_passes_through():
    score = calculate_score(_item(strategic_value=0.7), today=TODAY, available_hours=8, day_mode=None)
    assert score.factor_values[PriorityFactor.STRATEGIC_VALUE] == 0.7


def test_opportunity_value_passes_through():
    score = calculate_score(_item(opportunity_value=0.6), today=TODAY, available_hours=8, day_mode=None)
    assert score.factor_values[PriorityFactor.OPPORTUNITY_VALUE] == 0.6


def test_growth_value_passes_through():
    score = calculate_score(_item(growth_value=0.5), today=TODAY, available_hours=8, day_mode=None)
    assert score.factor_values[PriorityFactor.GROWTH_VALUE] == 0.5


def test_current_user_intent_is_binary():
    yes = calculate_score(_item(is_current_intent=True), today=TODAY, available_hours=8, day_mode=None)
    no = calculate_score(_item(is_current_intent=False), today=TODAY, available_hours=8, day_mode=None)
    assert yes.factor_values[PriorityFactor.CURRENT_USER_INTENT] == 1.0
    assert no.factor_values[PriorityFactor.CURRENT_USER_INTENT] == 0.0


def test_consequence_of_delay_passes_through():
    score = calculate_score(_item(consequence_of_delay=0.9), today=TODAY, available_hours=8, day_mode=None)
    assert score.factor_values[PriorityFactor.CONSEQUENCE_OF_DELAY] == 0.9


def test_available_time_favors_items_that_fit():
    fits = calculate_score(_item(estimated_hours=2), today=TODAY, available_hours=8, day_mode=None)
    does_not_fit = calculate_score(_item(estimated_hours=20), today=TODAY, available_hours=8, day_mode=None)
    assert fits.factor_values[PriorityFactor.AVAILABLE_TIME] > does_not_fit.factor_values[PriorityFactor.AVAILABLE_TIME]


def test_unknown_estimated_hours_is_neutral_not_penalized():
    score = calculate_score(_item(estimated_hours=None), today=TODAY, available_hours=8, day_mode=None)
    assert score.factor_values[PriorityFactor.AVAILABLE_TIME] == 0.5


# --- contextual (never permanent) ranking (§7) --------------------------------------------------


def test_no_domain_receives_a_structural_advantage_with_identical_factor_values():
    """§7: 'career > business > study > finance' must never be a
    hardcoded hierarchy - two candidates in different domains with
    identical factor values must rank identically."""
    career = _item("career", domain=LifeDomain.CAREER, strategic_value=0.7)
    study = _item("study", domain=LifeDomain.STUDY, strategic_value=0.7)
    ranking = rank_candidates((career, study), today=TODAY, available_hours=8, day_mode=None)
    assert ranking.core[0].total == ranking.core[1].total


def test_ranking_depends_on_what_the_items_actually_are_not_domain():
    """The same 'depends on what the two things are at the moment'
    principle, the other direction: a lower-value item in a normally
    'important' domain ranks below a higher-value item in another."""
    low_value_career = _item("career", domain=LifeDomain.CAREER, strategic_value=0.1)
    high_value_study = _item("study", domain=LifeDomain.STUDY, strategic_value=0.9, growth_value=0.9)
    ranking = rank_candidates((low_value_career, high_value_study), today=TODAY, available_hours=8, day_mode=None)
    assert ranking.core[0].item.item_id == "study"


# --- day mode influence (§12) ---------------------------------------------------------------------


def test_day_mode_alignment_boosts_matching_domain():
    item = _item(domain=LifeDomain.STUDY)
    with_mode = calculate_score(item, today=TODAY, available_hours=8, day_mode=DayMode(kind=DayModeKind.STUDY_FOCUSED))
    without_mode = calculate_score(item, today=TODAY, available_hours=8, day_mode=None)
    assert with_mode.factor_values[PriorityFactor.DAY_MODE_ALIGNMENT] > without_mode.factor_values[PriorityFactor.DAY_MODE_ALIGNMENT]


def test_day_mode_suppresses_work_domain_alignment():
    item = _item(domain=LifeDomain.BUSINESS)
    with_family_day = calculate_score(item, today=TODAY, available_hours=8, day_mode=DayMode(kind=DayModeKind.FAMILY_FOCUSED))
    without_mode = calculate_score(item, today=TODAY, available_hours=8, day_mode=None)
    assert with_family_day.factor_values[PriorityFactor.DAY_MODE_ALIGNMENT] < without_mode.factor_values[PriorityFactor.DAY_MODE_ALIGNMENT]


def test_family_domain_is_never_suppressed_by_family_focused_mode():
    item = _item(domain=LifeDomain.FAMILY)
    with_mode = calculate_score(item, today=TODAY, available_hours=8, day_mode=DayMode(kind=DayModeKind.FAMILY_FOCUSED))
    assert with_mode.factor_values[PriorityFactor.DAY_MODE_ALIGNMENT] > 0.5


def test_day_mode_does_not_permanently_change_the_candidate_itself():
    """§12: influences ranking only - the CandidateItem's own factor
    values are untouched by day mode."""
    item = _item(domain=LifeDomain.BUSINESS, strategic_value=0.7)
    calculate_score(item, today=TODAY, available_hours=8, day_mode=DayMode(kind=DayModeKind.FAMILY_FOCUSED))
    assert item.strategic_value == 0.7


# --- deterministic ranking / core 5 + optional 2 (§10) ---------------------------------------------


def test_rank_candidates_is_deterministic():
    items = tuple(_item(str(i), strategic_value=0.5) for i in range(6))
    r1 = rank_candidates(items, today=TODAY, available_hours=8, day_mode=None)
    r2 = rank_candidates(items, today=TODAY, available_hours=8, day_mode=None)
    assert [s.item.item_id for s in r1.core] == [s.item.item_id for s in r2.core]
    assert [s.total for s in r1.core] == [s.total for s in r2.core]


def test_default_output_is_core_five_plus_optional_two():
    items = tuple(_item(str(i)) for i in range(10))
    ranking = rank_candidates(items, today=TODAY, available_hours=8, day_mode=None)
    assert len(ranking.core) == 5
    assert len(ranking.optional) == 2


def test_fewer_than_five_candidates_never_pads_the_core():
    items = tuple(_item(str(i)) for i in range(3))
    ranking = rank_candidates(items, today=TODAY, available_hours=8, day_mode=None)
    assert len(ranking.core) == 3
    assert ranking.optional == ()


def test_never_a_twenty_item_dump():
    items = tuple(_item(str(i)) for i in range(20))
    ranking = rank_candidates(items, today=TODAY, available_hours=8, day_mode=None)
    assert len(ranking.core) + len(ranking.optional) <= 7


# --- explanation data (§8) -------------------------------------------------------------------------


def test_explain_produces_fact_inference_and_recommendation():
    score = calculate_score(_item(deadline=TODAY, strategic_value=0.9), today=TODAY, available_hours=8, day_mode=None)
    explanation = explain(score, today=TODAY)
    assert explanation.facts
    assert explanation.inference
    assert explanation.recommendation


def test_explain_states_the_deadline_as_a_fact():
    score = calculate_score(_item(deadline=TODAY), today=TODAY, available_hours=8, day_mode=None)
    explanation = explain(score, today=TODAY)
    assert any("deadline" in fact.lower() for fact in explanation.facts)


def test_explain_recommendation_language_is_a_suggestion_not_a_command():
    """§9: 'I suggest X', never 'You must do X.'"""
    score = calculate_score(_item(strategic_value=0.9), today=TODAY, available_hours=8, day_mode=None)
    explanation = explain(score, today=TODAY)
    assert "suggest" in explanation.recommendation.lower()
    assert "must" not in explanation.recommendation.lower()


# --- override: hold domains, never delete (§13, §21, §30) ------------------------------------------


def test_apply_override_holds_a_domain_and_re_ranks_the_rest():
    work = _item("work", domain=LifeDomain.CAREER, strategic_value=0.7)
    family = _item("family", domain=LifeDomain.FAMILY, strategic_value=0.5)
    result = apply_override((work, family), today=TODAY, available_hours=8, hold_domains=(LifeDomain.CAREER,))
    assert "work" not in [s.item.item_id for s in result.ranking.core]
    assert "family" in [s.item.item_id for s in result.ranking.core]


def test_apply_override_never_deletes_held_items_it_returns_them():
    work = _item("work", domain=LifeDomain.CAREER)
    result = apply_override((work,), today=TODAY, available_hours=8, hold_domains=(LifeDomain.CAREER,))
    assert result.held_items == (work,)


def test_apply_override_still_surfaces_a_genuinely_urgent_held_item():
    """§30: 'surfaces only genuinely time-sensitive items if necessary.'"""
    urgent_work = _item("urgent", domain=LifeDomain.CAREER, deadline=TODAY)
    result = apply_override((urgent_work,), today=TODAY, available_hours=8, hold_domains=(LifeDomain.CAREER,))
    assert result.held_items == ()
    assert [s.item.item_id for s in result.surfaced_despite_hold] == ["urgent"]


def test_apply_override_never_touches_domains_not_on_hold():
    business = _item("business", domain=LifeDomain.BUSINESS, strategic_value=0.5)
    result = apply_override((business,), today=TODAY, available_hours=8, hold_domains=(LifeDomain.CAREER,))
    assert result.held_items == ()
    assert business.item_id in [s.item.item_id for s in result.ranking.core]
