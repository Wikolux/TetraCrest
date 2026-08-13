"""candidate_sources.py (P5 §26): turning already-existing DailyIntent/
Mission/Pattern/Experiment records into CandidateItems - never a new
repository, never invented content."""

from datetime import date

from app.services.personal_os.candidate_sources import from_daily_intent, from_experiments, from_missions, from_pattern_recommendations
from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.experiment import Experiment, ExperimentBaseline
from app.services.personal_os.mission import Mission
from app.services.personal_os.pattern import Pattern, PatternEvidenceItem
from app.services.personal_os.reasoning import GrowthRecommendation, Hypothesis, InferredPattern, ObservedFact
from app.services.personal_os.shared.types import Confidence, DayType, ExperimentStatus, LifeDomain, MissionStatus, PatternStatus, PatternType

TODAY = date(2026, 8, 13)


def test_from_daily_intent_marks_every_activity_as_current_intent():
    intent = DailyIntent(
        intent_date=TODAY, stated_intention="x", day_type=DayType.MIXED,
        planned_activities=(PlannedActivity(description="Ship the report", deadline=TODAY),),
    )
    items = from_daily_intent(intent)
    assert len(items) == 1
    assert items[0].is_current_intent is True
    assert items[0].deadline == TODAY


def test_from_daily_intent_maps_focus_area_to_a_life_domain_when_it_matches():
    intent = DailyIntent(
        intent_date=TODAY, stated_intention="x", day_type=DayType.MIXED,
        planned_activities=(PlannedActivity(description="Apply to roles", focus_area="career"),),
    )
    items = from_daily_intent(intent)
    assert items[0].domain == LifeDomain.CAREER


def test_from_daily_intent_leaves_domain_none_when_focus_area_does_not_match_a_life_domain():
    intent = DailyIntent(
        intent_date=TODAY, stated_intention="x", day_type=DayType.MIXED,
        planned_activities=(PlannedActivity(description="Do the thing", focus_area="writing"),),
    )
    items = from_daily_intent(intent)
    assert items[0].domain is None


def test_from_daily_intent_handles_no_planned_activities():
    intent = DailyIntent(intent_date=TODAY, stated_intention="x", day_type=DayType.REST, is_rest_day=True)
    assert from_daily_intent(intent) == ()


def test_from_missions_only_includes_missions_with_a_next_step():
    with_next_step = Mission(mission_id="m1", objective="x", status=MissionStatus.ACTIVE, next_step="Research destinations")
    without_next_step = Mission(mission_id="m2", objective="y", status=MissionStatus.ACTIVE)
    items = from_missions((with_next_step, without_next_step))
    assert len(items) == 1
    assert items[0].description == "Research destinations"


def test_from_missions_carries_target_date_as_deadline():
    mission = Mission(mission_id="m1", objective="x", status=MissionStatus.ACTIVE, next_step="Book flights", target_date=date(2026, 12, 1))
    items = from_missions((mission,))
    assert items[0].deadline == date(2026, 12, 1)


def _confirmed_pattern_with_recommendation():
    facts = (ObservedFact(statement="fact one"), ObservedFact(statement="fact two"))
    inferred = InferredPattern(statement="pattern", supporting_facts=facts)
    hypothesis = Hypothesis(statement="hypothesis", explains=inferred)
    recommendation = GrowthRecommendation(statement="Add a buffer.", responds_to=hypothesis)
    return Pattern(
        pattern_id="p1", pattern_type=PatternType.REPEATED_POSTPONEMENT,
        observation_window_start=date(2026, 7, 1), observation_window_end=date(2026, 7, 14),
        evidence=(PatternEvidenceItem(observation_date=date(2026, 7, 1), activity_description="x", activity_category="learning", status="postponed"),),
        observed_facts=facts, pattern_statement="stmt", confidence=Confidence.MEDIUM,
        recommendation=recommendation, status=PatternStatus.CONFIRMED,
    )


def test_from_pattern_recommendations_only_includes_confirmed_patterns_with_a_recommendation():
    confirmed = _confirmed_pattern_with_recommendation()
    items = from_pattern_recommendations((confirmed,))
    assert len(items) == 1
    assert items[0].description == "Add a buffer."


def test_from_pattern_recommendations_excludes_unconfirmed_patterns():
    facts = (ObservedFact(statement="a"), ObservedFact(statement="b"))
    pending = Pattern(
        pattern_id="p2", pattern_type=PatternType.REPEATED_POSTPONEMENT,
        observation_window_start=date(2026, 7, 1), observation_window_end=date(2026, 7, 14),
        evidence=(PatternEvidenceItem(observation_date=date(2026, 7, 1), activity_description="x", activity_category="learning", status="postponed"),),
        observed_facts=facts, pattern_statement="stmt", confidence=Confidence.LOW,
        status=PatternStatus.PENDING_CONFIRMATION,
    )
    assert from_pattern_recommendations((pending,)) == ()


def test_from_experiments_only_includes_ready_for_review():
    baseline = ExperimentBaseline(metric="postponement_count", category="learning", period_start=date(2026, 7, 1), period_end=date(2026, 7, 14), value=4.0, observation_count=4)
    ready = Experiment(
        experiment_id="e1", pattern_id="p1", hypothesis_statement="h", adjustment="Add a buffer", measurement_plan="m",
        baseline=baseline, started_on=date(2026, 7, 16), review_date=date(2026, 7, 30), status=ExperimentStatus.READY_FOR_REVIEW,
    )
    active = Experiment(
        experiment_id="e2", pattern_id="p1", hypothesis_statement="h", adjustment="a", measurement_plan="m",
        baseline=baseline, started_on=date(2026, 7, 16), review_date=date(2026, 7, 30), status=ExperimentStatus.ACTIVE,
    )
    items = from_experiments((ready, active))
    assert len(items) == 1
    assert "Add a buffer" in items[0].description
