"""P6.3 - Chaotic-Day Validation: one deterministic, realistic day proving
every capability P6 claims, end to end, through the conversational seam
(P6.4) exactly as a user would actually type it - not just the
underlying functions in isolation.

Morning: Build TetraCrest, Study, Apply for jobs.
Then: an unexpected two-hour meeting: available time decreases; the user
adds a wife-related errand; postpones job applications; completes the
errand; the OS recalculates remaining priorities."""

from datetime import date

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.runtime.types import RuntimeResponse
from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.experiment_repository import InMemoryExperimentRepository
from app.services.personal_os.living_day import intent_activity_id
from app.services.personal_os.living_day_flow import LivingDayFlow
from app.services.personal_os.living_day_repository import InMemoryDayEventRepository
from app.services.personal_os.mission_repository import InMemoryMissionRepository
from app.services.personal_os.pattern_repository import InMemoryPatternRepository
from app.services.personal_os.priority_flow import PriorityIntelligenceFlow
from app.services.personal_os.repository import InMemoryDailyIntentRepository
from app.services.personal_os.shared.types import DayEventType, DayInteractionOutcome, DayType, LivingActivityStatus

ORG_ID, USER_ID = 1, 100
TODAY = date(2026, 8, 14)


class _FakeRuntime:
    def execute(self, request):
        return RuntimeResponse(success=False)


def test_the_chaotic_day_end_to_end():
    # --- setup: morning intent -----------------------------------------------------------------
    intent_repo = InMemoryDailyIntentRepository()
    mission_repo = InMemoryMissionRepository()
    pattern_repo = InMemoryPatternRepository()
    experiment_repo = InMemoryExperimentRepository()
    event_repo = InMemoryDayEventRepository()
    priority_flow = PriorityIntelligenceFlow(intent_repo, mission_repo, pattern_repo, experiment_repo, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()))
    flow = LivingDayFlow(intent_repo, event_repo, priority_flow)

    original_intent = DailyIntent(
        intent_date=TODAY,
        stated_intention="Build TetraCrest, study, apply for jobs",
        day_type=DayType.MIXED,
        planned_activities=(
            PlannedActivity(description="Build TetraCrest", estimated_hours=4),
            PlannedActivity(description="Study", estimated_hours=2),
            PlannedActivity(description="Apply for jobs", deadline=TODAY, estimated_hours=1),
        ),
    )
    intent_repo.save(original_intent, organization_id=ORG_ID, user_id=USER_ID)

    apply_id = intent_activity_id(TODAY, "Apply for jobs")

    baseline_ranking = flow.replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8.0)
    baseline_core_descriptions = {s.item.description for s in baseline_ranking.core}
    assert baseline_core_descriptions == {"Build TetraCrest", "Study", "Apply for jobs"}

    # --- 1. an unexpected two-hour meeting appears / 2. available time decreases ----------------
    meeting_result = flow.apply_statement(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, user_text="I have an unexpected meeting for two hours.")
    assert meeting_result.outcome == DayInteractionOutcome.EVENTS_RECORDED

    state_after_meeting = flow.get_state(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    assert state_after_meeting.available_hours == 6.0  # 8 - 2

    # --- 3. user adds: "Buy something for my wife on my way home." -------------------------------
    errand_result = flow.apply_statement(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, user_text="Add buying something for my wife on my way home.")
    assert errand_result.outcome == DayInteractionOutcome.EVENTS_RECORDED
    errand_activity_id = errand_result.events[0].activity_id

    # --- 4. user postpones job applications -------------------------------------------------------
    postpone_result = flow.apply_statement(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, user_text="Postpone applying for jobs.")
    assert postpone_result.outcome == DayInteractionOutcome.EVENTS_RECORDED
    assert postpone_result.events[0].activity_id == apply_id

    # --- 5. wife-related errand becomes relevant (already active - check ranking includes it) ----
    state_mid_day = flow.get_state(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    assert state_mid_day.find(errand_activity_id).status == LivingActivityStatus.ACTIVE
    assert state_mid_day.find(apply_id).status == LivingActivityStatus.POSTPONED

    mid_day_ranking = flow.replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    mid_day_core_descriptions = {s.item.description for s in mid_day_ranking.core}
    assert "buy" in " ".join(mid_day_core_descriptions).lower() or any("wife" in d.lower() for d in mid_day_core_descriptions)
    assert "Apply for jobs" not in mid_day_core_descriptions  # postponed work is not resurfaced

    # --- 6. user completes the errand ---------------------------------------------------------------
    complete_result = flow.apply_statement(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, user_text="I'm done with buying something for my wife.")
    assert complete_result.outcome == DayInteractionOutcome.EVENTS_RECORDED
    assert complete_result.events[0].activity_id == errand_activity_id

    # --- 7. OS recalculates remaining priorities -----------------------------------------------------
    final_ranking = flow.replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    final_core_descriptions = {s.item.description for s in final_ranking.core}

    # --- REQUIRED PROOFS (P6.3) --------------------------------------------------------------------

    # the original morning intent remains preserved
    final_state = flow.get_state(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    assert final_state.original_intent is not None
    assert final_state.original_intent.stated_intention == "Build TetraCrest, study, apply for jobs"
    assert final_state.original_intent.planned_activities == original_intent.planned_activities

    # the meeting is recorded as a later event
    meeting_events = [e for e in final_state.events if e.event_type == DayEventType.UNEXPECTED_EVENT]
    assert len(meeting_events) == 1
    assert meeting_events[0].sequence > 0  # recorded after the day began, not part of the original intent

    # the new errand exists in the current day
    errand_activity = final_state.find(errand_activity_id)
    assert errand_activity is not None
    assert "wife" in errand_activity.description.lower()

    # postponed work is not incorrectly resurfaced as today's active work
    assert final_state.find(apply_id).status == LivingActivityStatus.POSTPONED
    assert "Apply for jobs" not in final_core_descriptions

    # completed work is not recommended again
    assert final_state.find(errand_activity_id).status == LivingActivityStatus.COMPLETED
    assert not any("wife" in d.lower() for d in final_core_descriptions)

    # remaining priorities change after the interruption
    assert final_core_descriptions != baseline_core_descriptions
    assert final_core_descriptions == {"Build TetraCrest", "Study"}

    # the system never makes the final decision for the user - replan()/get_state() never write
    events_before_extra_replans = len(event_repo.list_for_day(organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY))
    flow.replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    flow.replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    flow.get_state(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    assert len(event_repo.list_for_day(organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)) == events_before_extra_replans

    # the complete change history can be reconstructed
    full_history = event_repo.list_for_day(organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)
    assert len(full_history) >= 5  # meeting, time-changed, errand-added, postponed, completed (at minimum)
    reconstructed_independently = intent_repo.get_for_date(organization_id=ORG_ID, user_id=USER_ID, intent_date=TODAY)
    from app.services.personal_os.living_day import reconstruct

    replayed_state = reconstruct(reconstructed_independently, full_history, day_date=TODAY)
    assert replayed_state.activities == final_state.activities
    assert replayed_state.available_hours == final_state.available_hours


def test_status_query_mid_chaos_never_alters_history():
    """§30 combined with §P6.4: asking 'what's the plan?' at any point
    during a chaotic day must never itself become part of the chaos."""
    intent_repo = InMemoryDailyIntentRepository()
    mission_repo = InMemoryMissionRepository()
    pattern_repo = InMemoryPatternRepository()
    experiment_repo = InMemoryExperimentRepository()
    event_repo = InMemoryDayEventRepository()
    priority_flow = PriorityIntelligenceFlow(intent_repo, mission_repo, pattern_repo, experiment_repo, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()))
    flow = LivingDayFlow(intent_repo, event_repo, priority_flow)

    intent_repo.save(
        DailyIntent(intent_date=TODAY, stated_intention="x", day_type=DayType.MIXED, planned_activities=(PlannedActivity(description="Build TetraCrest"),)),
        organization_id=ORG_ID, user_id=USER_ID,
    )
    flow.apply_statement(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, user_text="I have a meeting for one hour.")
    count_after_meeting = len(event_repo.list_for_day(organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY))

    flow.apply_statement(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, user_text="What's the plan?")
    flow.apply_statement(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, user_text="What's the plan?")

    assert len(event_repo.list_for_day(organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)) == count_after_meeting


def test_a_day_that_starts_with_no_morning_plan_at_all_is_valid():
    """§ 'I don't have plans today' / 'I don't know yet' - all should be
    valid starting states, not errors."""
    intent_repo = InMemoryDailyIntentRepository()
    mission_repo = InMemoryMissionRepository()
    pattern_repo = InMemoryPatternRepository()
    experiment_repo = InMemoryExperimentRepository()
    event_repo = InMemoryDayEventRepository()
    priority_flow = PriorityIntelligenceFlow(intent_repo, mission_repo, pattern_repo, experiment_repo, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()))
    flow = LivingDayFlow(intent_repo, event_repo, priority_flow)

    state = flow.get_state(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    assert state.original_intent is None
    assert state.activities == ()

    result = flow.apply_statement(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, user_text="Add going for a walk.")
    assert result.outcome == DayInteractionOutcome.EVENTS_RECORDED

    ranking = flow.replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8.0)
    assert any(s.item.description == "going for a walk" for s in ranking.core)
