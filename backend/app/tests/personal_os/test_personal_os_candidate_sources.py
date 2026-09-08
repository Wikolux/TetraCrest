"""candidate_sources.py (P5 §26): turning already-existing DailyIntent/
Mission/Pattern/Experiment records into CandidateItems - never a new
repository, never invented content."""

from datetime import date

from app.services.personal_os.candidate_sources import apply_adopted_priority_effects, from_daily_intent, from_experiments, from_living_day_state, from_missions, from_pattern_recommendations
from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.experiment import Experiment, ExperimentBaseline
from app.services.personal_os.living_day import DayEvent, reconstruct
from app.services.personal_os.mission import Mission
from app.services.personal_os.pattern import Pattern, PatternEvidenceItem
from app.services.personal_os.priority import CandidateItem
from app.services.personal_os.reasoning import GrowthRecommendation, Hypothesis, InferredPattern, ObservedFact
from app.services.personal_os.shared.types import Confidence, DayEventType, DayType, ExperimentStatus, LifeDomain, MissionStatus, PatternStatus, PatternType, PriorityDirection

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


# --- from_living_day_state (P6.2) ---------------------------------------------------------------


def test_from_living_day_state_includes_only_active_activities():
    intent = DailyIntent(intent_date=TODAY, stated_intention="x", day_type=DayType.MIXED, planned_activities=(PlannedActivity(description="Build Tetra"),))
    activity_id = f"intent:{TODAY.isoformat()}:Build Tetra"
    events = (DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED, activity_id=activity_id, sequence=1),)
    state = reconstruct(intent, events, day_date=TODAY)
    assert from_living_day_state(state) == ()


def test_from_living_day_state_marks_items_as_current_intent():
    intent = DailyIntent(intent_date=TODAY, stated_intention="x", day_type=DayType.MIXED, planned_activities=(PlannedActivity(description="Build Tetra"),))
    state = reconstruct(intent, (), day_date=TODAY)
    items = from_living_day_state(state)
    assert len(items) == 1
    assert items[0].is_current_intent is True


def test_from_living_day_state_excludes_unexpected_events():
    events = (DayEvent(event_type=DayEventType.UNEXPECTED_EVENT, activity_id="m1", description="Meeting", sequence=1),)
    state = reconstruct(None, events, day_date=TODAY)
    assert from_living_day_state(state) == ()


def test_from_living_day_state_includes_mid_day_additions():
    events = (DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="Buy a gift", sequence=1),)
    state = reconstruct(None, events, day_date=TODAY)
    items = from_living_day_state(state)
    assert len(items) == 1
    assert items[0].description == "Buy a gift"
    assert items[0].source == "living_day"


# --- apply_adopted_priority_effects (P7.11): the one place an ADOPTED effect touches a candidate ----


def test_apply_adopted_priority_effects_is_a_no_op_with_no_applicable_effects():
    items = (CandidateItem(item_id="mission:m1", description="x", domain=LifeDomain.CAREER, source="mission", source_id="m1"),)
    result = apply_adopted_priority_effects(items, domain_effects={}, mission_effects={}, boost_magnitude=0.3)
    assert result == items


def test_apply_adopted_priority_effects_boosts_momentum_for_a_matching_domain():
    items = (CandidateItem(item_id="mission:m1", description="x", domain=LifeDomain.CAREER, momentum=0.0, source="mission", source_id="m1"),)
    result = apply_adopted_priority_effects(items, domain_effects={LifeDomain.CAREER: PriorityDirection.BOOST}, mission_effects={}, boost_magnitude=0.3)
    assert result[0].momentum == 0.3


def test_apply_adopted_priority_effects_suppresses_momentum_for_a_matching_domain():
    items = (CandidateItem(item_id="mission:m1", description="x", domain=LifeDomain.FINANCE_INVESTMENTS, momentum=0.5, source="mission", source_id="m1"),)
    result = apply_adopted_priority_effects(items, domain_effects={LifeDomain.FINANCE_INVESTMENTS: PriorityDirection.SUPPRESS}, mission_effects={}, boost_magnitude=0.3)
    assert result[0].momentum == 0.2


def test_apply_adopted_priority_effects_clamps_to_the_valid_range():
    items = (CandidateItem(item_id="pattern:p1", description="x", momentum=0.9, domain=LifeDomain.CAREER, source="pattern", source_id="p1"),)
    result = apply_adopted_priority_effects(items, domain_effects={LifeDomain.CAREER: PriorityDirection.BOOST}, mission_effects={}, boost_magnitude=0.3)
    assert result[0].momentum == 1.0


def test_apply_adopted_priority_effects_ignores_non_matching_candidates():
    items = (CandidateItem(item_id="mission:m1", description="x", domain=LifeDomain.STUDY, momentum=0.4, source="mission", source_id="m1"),)
    result = apply_adopted_priority_effects(items, domain_effects={LifeDomain.CAREER: PriorityDirection.BOOST}, mission_effects={}, boost_magnitude=0.3)
    assert result[0].momentum == 0.4


def test_apply_adopted_priority_effects_a_mission_specific_effect_takes_precedence_over_domain():
    items = (CandidateItem(item_id="mission:m1", description="x", domain=LifeDomain.CAREER, momentum=0.0, source="mission", source_id="m1"),)
    result = apply_adopted_priority_effects(
        items,
        domain_effects={LifeDomain.CAREER: PriorityDirection.BOOST},
        mission_effects={"m1": PriorityDirection.SUPPRESS},
        boost_magnitude=0.3,
    )
    assert result[0].momentum == 0.0


def test_apply_adopted_priority_effects_never_touches_current_intent_candidates_when_not_given_to_it():
    """This function itself has no notion of is_current_intent - the
    guarantee that explicit intent is never adjusted comes from
    priority_flow.gather_non_intent_candidates() never passing intent
    candidates through this function at all (see
    test_personal_os_priority_flow.py)."""
    items = (CandidateItem(item_id="intent:x", description="x", domain=LifeDomain.CAREER, is_current_intent=True, momentum=0.0, source="daily_intent"),)
    result = apply_adopted_priority_effects(items, domain_effects={LifeDomain.CAREER: PriorityDirection.BOOST}, mission_effects={}, boost_magnitude=0.3)
    assert result[0].momentum == 0.3
