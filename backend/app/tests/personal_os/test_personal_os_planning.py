"""Adaptive planning (§7): recommendations only, deterministic, never
auto-applied."""

from datetime import date

from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.planning import AdaptivePlanner, PlanRecommendation
from app.services.personal_os.reconciliation import ReconciliationEvidence, reconcile
from app.services.personal_os.shared.types import DayType, RecommendationKind


def _intent(day_type=DayType.WORK, is_rest_day=False):
    return DailyIntent(intent_date=date(2026, 8, 13), stated_intention="x", day_type=day_type, is_rest_day=is_rest_day)


def test_rest_day_produces_a_protect_rest_recommendation_only():
    intent = _intent(day_type=DayType.REST, is_rest_day=True)
    recs = AdaptivePlanner().recommend(intent, reconciliations=())
    assert len(recs) == 1
    assert recs[0].kind == RecommendationKind.PROTECT_REST


def test_blocked_item_produces_a_move_recommendation():
    activity = PlannedActivity(description="Waiting on client feedback")
    record = reconcile(activity, ReconciliationEvidence(explicitly_blocked=True))
    recs = AdaptivePlanner().recommend(_intent(), (record,))
    assert any(r.kind == RecommendationKind.MOVE for r in recs)


def test_postponed_item_produces_a_resequence_recommendation():
    activity = PlannedActivity(description="Write the report")
    record = reconcile(activity, ReconciliationEvidence(explicitly_postponed=True))
    recs = AdaptivePlanner().recommend(_intent(), (record,))
    assert any(r.kind == RecommendationKind.RESEQUENCE for r in recs)


def test_superseded_item_produces_a_reprioritize_recommendation():
    activity = PlannedActivity(description="Old priority")
    record = reconcile(activity, ReconciliationEvidence(superseding_priority="New priority"))
    recs = AdaptivePlanner().recommend(_intent(), (record,))
    assert any(r.kind == RecommendationKind.REPRIORITIZE for r in recs)


def test_completed_item_produces_no_recommendation():
    activity = PlannedActivity(description="Done thing")
    record = reconcile(activity, ReconciliationEvidence(explicitly_completed=True))
    recs = AdaptivePlanner().recommend(_intent(), (record,))
    assert recs == ()


def test_adaptive_planning_produces_deterministic_recommendations_from_the_same_state():
    activity = PlannedActivity(description="Repeatable")
    record = reconcile(activity, ReconciliationEvidence(explicitly_blocked=True))
    intent = _intent()

    first = AdaptivePlanner().recommend(intent, (record,))
    second = AdaptivePlanner().recommend(intent, (record,))
    assert first == second


def test_recommendations_are_never_auto_applied_by_construction():
    """A PlanRecommendation is only ever data - there is no method on it,
    or on AdaptivePlanner, that mutates a DailyIntent or a repository."""
    assert not hasattr(PlanRecommendation, "apply")
    assert not hasattr(AdaptivePlanner, "apply")


def test_plan_recommendation_requires_a_rationale():
    import pytest

    with pytest.raises(ValueError):
        PlanRecommendation(kind=RecommendationKind.MOVE, subject="x", rationale="")
