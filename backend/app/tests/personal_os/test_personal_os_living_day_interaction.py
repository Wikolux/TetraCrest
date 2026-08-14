"""Conversational interaction seam (P6.4): every worked example named in
the build brief, plus the ambiguity-must-ask-not-guess requirement and
the read-only status-query guarantee."""

from datetime import date

from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.living_day import intent_activity_id, reconstruct
from app.services.personal_os.living_day_interaction import HeuristicDayInteractionInterpreter
from app.services.personal_os.shared.types import DayEventType, DayInteractionOutcome, DayModeKind, DayType

TODAY = date(2026, 8, 14)


def _state(*activities, events=()):
    intent = DailyIntent(intent_date=TODAY, stated_intention="x", day_type=DayType.MIXED, planned_activities=activities) if activities else None
    return reconstruct(intent, events, day_date=TODAY)


def _interpreter():
    return HeuristicDayInteractionInterpreter()


# --- the seven worked examples from the build brief, verbatim ------------------------------------


def test_unexpected_meeting_with_duration():
    state = _state()
    result = _interpreter().interpret("I have a meeting for two hours.", state=state)
    assert result.outcome == DayInteractionOutcome.EVENTS_RECORDED
    types = [e.event_type for e in result.events]
    assert DayEventType.UNEXPECTED_EVENT in types
    assert DayEventType.AVAILABLE_TIME_CHANGED in types
    time_event = next(e for e in result.events if e.event_type == DayEventType.AVAILABLE_TIME_CHANGED)
    assert time_event.available_hours == state.available_hours - 2.0


def test_add_an_errand():
    state = _state()
    result = _interpreter().interpret("Add buying something for my wife.", state=state)
    assert result.outcome == DayInteractionOutcome.EVENTS_RECORDED
    assert len(result.events) == 1
    assert result.events[0].event_type == DayEventType.ACTIVITY_ADDED
    assert "buying something for my wife" in result.events[0].description.lower()


def test_complete_an_activity_by_partial_name():
    state = _state(PlannedActivity(description="Build Tetra Crest"))
    result = _interpreter().interpret("I'm done with Build Tetra.", state=state)
    assert result.outcome == DayInteractionOutcome.EVENTS_RECORDED
    assert result.events[0].event_type == DayEventType.ACTIVITY_COMPLETED
    assert result.events[0].activity_id == intent_activity_id(TODAY, "Build Tetra Crest")


def test_postpone_an_activity_by_partial_name():
    state = _state(PlannedActivity(description="Study system design"))
    result = _interpreter().interpret("Postpone studying.", state=state)
    assert result.outcome == DayInteractionOutcome.EVENTS_RECORDED
    assert result.events[0].event_type == DayEventType.ACTIVITY_POSTPONED
    assert result.events[0].activity_id == intent_activity_id(TODAY, "Study system design")


def test_hold_everything_and_switch_to_family_day():
    state = _state(PlannedActivity(description="Build Tetra Crest"), PlannedActivity(description="Study system design"))
    result = _interpreter().interpret("Hold everything; today is a family day.", state=state)
    assert result.outcome == DayInteractionOutcome.EVENTS_RECORDED
    hold_events = [e for e in result.events if e.event_type == DayEventType.ACTIVITY_HELD]
    mode_events = [e for e in result.events if e.event_type == DayEventType.DAY_MODE_CHANGED]
    assert len(hold_events) == 2
    assert len(mode_events) == 1
    assert mode_events[0].day_mode.kind == DayModeKind.FAMILY_FOCUSED


def test_resume_the_things_i_paused():
    intent = DailyIntent(intent_date=TODAY, stated_intention="x", day_type=DayType.MIXED, planned_activities=(PlannedActivity(description="Build Tetra Crest"),))
    activity_id = intent_activity_id(TODAY, "Build Tetra Crest")
    from app.services.personal_os.living_day import DayEvent

    held_state = reconstruct(intent, (DayEvent(event_type=DayEventType.ACTIVITY_HELD, activity_id=activity_id, sequence=1),), day_date=TODAY)
    result = _interpreter().interpret("Resume the things I paused.", state=held_state)
    assert result.outcome == DayInteractionOutcome.EVENTS_RECORDED
    assert len(result.events) == 1
    assert result.events[0].event_type == DayEventType.ACTIVITY_RESUMED
    assert result.events[0].activity_id == activity_id


def test_whats_the_plan_is_read_only():
    state = _state(PlannedActivity(description="Build Tetra Crest"))
    result = _interpreter().interpret("What's the plan?", state=state)
    assert result.outcome == DayInteractionOutcome.STATUS_QUERY
    assert result.events == ()


# --- ambiguity: never guess, always ask (P6.4) ----------------------------------------------------


def test_ambiguous_target_asks_for_clarification_instead_of_guessing():
    state = _state(PlannedActivity(description="Call John about the proposal"), PlannedActivity(description="Call John re the invoice"))
    result = _interpreter().interpret("Postpone Call John.", state=state)
    assert result.outcome == DayInteractionOutcome.CLARIFICATION_NEEDED
    assert result.events == ()
    assert len(result.candidates) == 2
    assert result.clarification_question


def test_unambiguous_target_among_similar_activities_is_not_flagged():
    state = _state(PlannedActivity(description="Call John about the proposal"), PlannedActivity(description="Email Sarah the report"))
    result = _interpreter().interpret("Postpone Call John.", state=state)
    assert result.outcome == DayInteractionOutcome.EVENTS_RECORDED


def test_unrecognized_target_is_never_guessed():
    state = _state(PlannedActivity(description="Build Tetra Crest"))
    result = _interpreter().interpret("Postpone the quantum thing.", state=state)
    assert result.outcome == DayInteractionOutcome.UNRECOGNIZED
    assert result.events == ()


# --- read-only guarantee: status query never appends (P6.4) ---------------------------------------


def test_status_query_never_creates_a_new_persisted_version():
    from app.services.personal_os.living_day_flow import LivingDayFlow
    from app.services.personal_os.living_day_repository import InMemoryDayEventRepository
    from app.services.personal_os.repository import InMemoryDailyIntentRepository
    from app.services.personal_os.mission_repository import InMemoryMissionRepository
    from app.services.personal_os.pattern_repository import InMemoryPatternRepository
    from app.services.personal_os.experiment_repository import InMemoryExperimentRepository
    from app.services.personal_os.priority_flow import PriorityIntelligenceFlow

    intent_repo = InMemoryDailyIntentRepository()
    intent_repo.save(
        DailyIntent(intent_date=TODAY, stated_intention="x", day_type=DayType.MIXED, planned_activities=(PlannedActivity(description="Build Tetra Crest"),)),
        organization_id=1, user_id=1,
    )
    event_repo = InMemoryDayEventRepository()
    priority_flow = PriorityIntelligenceFlow(intent_repo, InMemoryMissionRepository(), InMemoryPatternRepository(), InMemoryExperimentRepository())
    flow = LivingDayFlow(intent_repo, event_repo, priority_flow)

    flow.apply_statement(organization_id=1, user_id=1, today=TODAY, user_text="What's the plan?")
    assert event_repo.list_for_day(organization_id=1, user_id=1, day_date=TODAY) == ()


def test_clarification_needed_also_never_appends():
    from app.services.personal_os.living_day_flow import LivingDayFlow
    from app.services.personal_os.living_day_repository import InMemoryDayEventRepository
    from app.services.personal_os.repository import InMemoryDailyIntentRepository
    from app.services.personal_os.mission_repository import InMemoryMissionRepository
    from app.services.personal_os.pattern_repository import InMemoryPatternRepository
    from app.services.personal_os.experiment_repository import InMemoryExperimentRepository
    from app.services.personal_os.priority_flow import PriorityIntelligenceFlow

    intent_repo = InMemoryDailyIntentRepository()
    intent_repo.save(
        DailyIntent(
            intent_date=TODAY, stated_intention="x", day_type=DayType.MIXED,
            planned_activities=(PlannedActivity(description="Call John about the proposal"), PlannedActivity(description="Call John re the invoice")),
        ),
        organization_id=1, user_id=1,
    )
    event_repo = InMemoryDayEventRepository()
    priority_flow = PriorityIntelligenceFlow(intent_repo, InMemoryMissionRepository(), InMemoryPatternRepository(), InMemoryExperimentRepository())
    flow = LivingDayFlow(intent_repo, event_repo, priority_flow)

    result = flow.apply_statement(organization_id=1, user_id=1, today=TODAY, user_text="Postpone Call John.")
    assert result.outcome == DayInteractionOutcome.CLARIFICATION_NEEDED
    assert event_repo.list_for_day(organization_id=1, user_id=1, day_date=TODAY) == ()


# --- edge cases ------------------------------------------------------------------------------------


def test_empty_statement_is_unrecognized_not_an_error():
    result = _interpreter().interpret("", state=_state())
    assert result.outcome == DayInteractionOutcome.UNRECOGNIZED


def test_hold_all_with_no_active_activities_still_applies_day_mode_change():
    state = _state()
    result = _interpreter().interpret("Hold everything; today is a family day.", state=state)
    assert result.outcome == DayInteractionOutcome.EVENTS_RECORDED
    assert len(result.events) == 1
    assert result.events[0].event_type == DayEventType.DAY_MODE_CHANGED


def test_add_without_a_description_is_unrecognized():
    result = _interpreter().interpret("Add", state=_state())
    assert result.outcome == DayInteractionOutcome.UNRECOGNIZED


def test_meeting_without_a_stated_duration_records_no_time_change():
    state = _state()
    result = _interpreter().interpret("I have an unexpected meeting.", state=state)
    assert result.outcome == DayInteractionOutcome.EVENTS_RECORDED
    types = [e.event_type for e in result.events]
    assert DayEventType.UNEXPECTED_EVENT in types
    assert DayEventType.AVAILABLE_TIME_CHANGED not in types
