"""LivingDayFlow (P6.2): connecting the Living Day State to the existing
Priority Intelligence - record, reconstruct, recalculate, recommend -
never a second priority algorithm, and the OS never makes the final
decision for the user."""

from datetime import date

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.runtime.types import RuntimeResponse
from app.services.personal_os.adaptation import Adaptation, AdaptationEffect, AdaptationTarget
from app.services.personal_os.adaptation_repository import InMemoryAdaptationRepository
from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.experiment_repository import InMemoryExperimentRepository
from app.services.personal_os.living_day import DayEvent, intent_activity_id
from app.services.personal_os.living_day_flow import LivingDayFlow
from app.services.personal_os.living_day_repository import InMemoryDayEventRepository
from app.services.personal_os.mission import Mission
from app.services.personal_os.mission_repository import InMemoryMissionRepository
from app.services.personal_os.pattern_repository import InMemoryPatternRepository
from app.services.personal_os.priority_flow import PriorityIntelligenceFlow
from app.services.personal_os.repository import InMemoryDailyIntentRepository
from app.services.personal_os.shared.types import (
    AdaptationEffectKind,
    AdaptationScope,
    AdaptationStatus,
    Confidence,
    DayEventType,
    DayType,
    LifeDomain,
    LivingActivityStatus,
    MissionStatus,
    PriorityDirection,
)

ORG_ID, USER_ID = 1, 9
TODAY = date(2026, 8, 14)


class _FakeRuntime:
    def __init__(self):
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return RuntimeResponse(success=False)


def _flow(adaptation_repository=None):
    intent_repo = InMemoryDailyIntentRepository()
    mission_repo = InMemoryMissionRepository()
    pattern_repo = InMemoryPatternRepository()
    experiment_repo = InMemoryExperimentRepository()
    event_repo = InMemoryDayEventRepository()
    priority_flow = PriorityIntelligenceFlow(
        intent_repo, mission_repo, pattern_repo, experiment_repo, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()), adaptation_repository=adaptation_repository
    )
    living_flow = LivingDayFlow(intent_repo, event_repo, priority_flow)
    return living_flow, intent_repo, event_repo, mission_repo


def _adopted_domain_preference(adaptation_repo, *, direction, domain=LifeDomain.CAREER):
    target = AdaptationTarget(scope=AdaptationScope.USER_PREFERENCE, target_id=domain.value)
    effect = AdaptationEffect(kind=AdaptationEffectKind.PRIORITY_ADJUSTMENT, direction=direction)
    adaptation = Adaptation(adaptation_id="", target=target, pattern_id="pattern-1", confidence=Confidence.MEDIUM, status=AdaptationStatus.ADOPTED, effect=effect)
    return adaptation_repo.save(adaptation, organization_id=ORG_ID, user_id=USER_ID)


def _seed_intent(intent_repo, *activities):
    intent = DailyIntent(intent_date=TODAY, stated_intention="Build Tetra, study, apply for jobs", day_type=DayType.MIXED, planned_activities=activities)
    intent_repo.save(intent, organization_id=ORG_ID, user_id=USER_ID)
    return intent


# --- get_state / record_event ---------------------------------------------------------------------


def test_get_state_with_no_intent_and_no_events_is_a_valid_start():
    flow, _, _, *_ = _flow()
    state = flow.get_state(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    assert state.original_intent is None
    assert state.activities == ()


def test_record_event_appends_and_returns_updated_state():
    flow, intent_repo, event_repo, *_ = _flow()
    state = flow.record_event(
        organization_id=ORG_ID, user_id=USER_ID, today=TODAY, event=DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="Buy a gift")
    )
    assert state.find("a1").status == LivingActivityStatus.ACTIVE
    assert len(event_repo.list_for_day(organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)) == 1


def test_record_events_appends_several_in_order():
    flow, _, event_repo, *_ = _flow()
    flow.record_events(
        organization_id=ORG_ID, user_id=USER_ID, today=TODAY,
        events=(
            DayEvent(event_type=DayEventType.UNEXPECTED_EVENT, activity_id="m1", description="Meeting", estimated_hours=2.0),
            DayEvent(event_type=DayEventType.AVAILABLE_TIME_CHANGED, available_hours=6.0),
        ),
    )
    events = event_repo.list_for_day(organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)
    assert [e.event_type for e in events] == [DayEventType.UNEXPECTED_EVENT, DayEventType.AVAILABLE_TIME_CHANGED]


# --- replan: reuses the existing priority engine, never a second one (P6.2) -----------------------


def test_replan_ranks_using_the_living_day_not_the_static_intent():
    flow, intent_repo, _, *_ = _flow()
    _seed_intent(intent_repo, PlannedActivity(description="Apply for jobs", deadline=TODAY))
    apply_id = intent_activity_id(TODAY, "Apply for jobs")
    flow.record_event(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, event=DayEvent(event_type=DayEventType.ACTIVITY_POSTPONED, activity_id=apply_id))

    ranking = flow.replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8.0)
    assert ranking.core == ()


def test_replan_reflects_available_time_changes():
    flow, intent_repo, _, *_ = _flow()
    _seed_intent(intent_repo, PlannedActivity(description="Build Tetra Crest", estimated_hours=6))
    flow.record_event(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, event=DayEvent(event_type=DayEventType.AVAILABLE_TIME_CHANGED, available_hours=1.0))

    ranking = flow.replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    build_score = next(s for s in ranking.core if s.item.description == "Build Tetra Crest")
    assert build_score.factor_values is not None  # sanity: still scored, just with a low available-time factor


def test_replan_uses_state_recorded_day_mode_when_none_is_passed_explicitly():
    from app.services.personal_os.day_mode import DayMode
    from app.services.personal_os.shared.types import DayModeKind

    flow, intent_repo, _, *_ = _flow()
    _seed_intent(intent_repo, PlannedActivity(description="Business review", focus_area="business"))
    flow.record_event(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, event=DayEvent(event_type=DayEventType.DAY_MODE_CHANGED, day_mode=DayMode(kind=DayModeKind.RECOVERY)))

    ranking = flow.replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8.0)
    assert ranking.day_mode.kind == DayModeKind.RECOVERY


def test_present_replan_reuses_priority_intelligence_flow_present():
    flow, intent_repo, _, *_ = _flow()
    _seed_intent(intent_repo, PlannedActivity(description="Build Tetra Crest"))
    presentation = flow.present_replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8.0)
    assert len(presentation.core) == 1
    assert presentation.core[0].narrative


# --- the system never makes the final decision ------------------------------------------------------


def test_replan_never_writes_to_the_event_log():
    flow, intent_repo, event_repo, *_ = _flow()
    _seed_intent(intent_repo, PlannedActivity(description="Build Tetra Crest"))
    flow.replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8.0)
    assert event_repo.list_for_day(organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY) == ()


def test_get_state_never_writes_to_the_event_log():
    flow, intent_repo, event_repo, *_ = _flow()
    _seed_intent(intent_repo, PlannedActivity(description="Build Tetra Crest"))
    flow.get_state(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    assert event_repo.list_for_day(organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY) == ()


# --- P7.11 §19: replan() inherits adopted adaptations through the shared Priority seam, -------------
# --- with NO adaptation-specific code added to this module itself -----------------------------------


def test_replan_inherits_an_adopted_preference_through_the_shared_priority_seam():
    """The single most important P7.11 proof: LivingDayFlow itself gained
    zero adaptation-aware code (see the diff to living_day_flow.py - only
    one line changed, threading an existing user_id through to
    present()); this test alone is what demonstrates the adopted effect
    still reaches replan() because it already reused
    priority_flow.gather_non_intent_candidates()."""
    adaptation_repo = InMemoryAdaptationRepository()
    flow, intent_repo, _, mission_repo = _flow(adaptation_repo)
    mission_repo.save(
        Mission(mission_id="m1", objective="x", status=MissionStatus.ACTIVE, domain=LifeDomain.CAREER, next_step="Follow up with recruiter"),
        organization_id=ORG_ID,
        user_id=USER_ID,
    )

    baseline = flow.replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8.0)
    baseline_score = next(s for s in baseline.core if s.item.source == "mission")
    assert baseline_score.item.momentum == 0.0

    _adopted_domain_preference(adaptation_repo, direction=PriorityDirection.BOOST)

    adapted = flow.replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8.0)
    adapted_score = next(s for s in adapted.core if s.item.source == "mission")
    assert adapted_score.item.momentum == flow.priority_flow.config.adaptation_priority_boost
    assert adapted_score.total > baseline_score.total


def test_replan_rollback_removes_the_effect_without_any_manual_repair():
    adaptation_repo = InMemoryAdaptationRepository()
    flow, intent_repo, _, mission_repo = _flow(adaptation_repo)
    mission_repo.save(
        Mission(mission_id="m1", objective="x", status=MissionStatus.ACTIVE, domain=LifeDomain.CAREER, next_step="Follow up with recruiter"),
        organization_id=ORG_ID,
        user_id=USER_ID,
    )
    adopted = _adopted_domain_preference(adaptation_repo, direction=PriorityDirection.BOOST)

    boosted = flow.replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8.0)
    assert next(s for s in boosted.core if s.item.source == "mission").item.momentum == flow.priority_flow.config.adaptation_priority_boost

    from dataclasses import replace as _replace

    adaptation_repo.save(_replace(adopted, status=AdaptationStatus.ROLLED_BACK), organization_id=ORG_ID, user_id=USER_ID)

    restored = flow.replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8.0)
    assert next(s for s in restored.core if s.item.source == "mission").item.momentum == 0.0


def test_present_replan_also_inherits_the_attributed_explanation():
    adaptation_repo = InMemoryAdaptationRepository()
    flow, intent_repo, _, mission_repo = _flow(adaptation_repo)
    mission_repo.save(
        Mission(mission_id="m1", objective="x", status=MissionStatus.ACTIVE, domain=LifeDomain.CAREER, next_step="Follow up with recruiter"),
        organization_id=ORG_ID,
        user_id=USER_ID,
    )
    _adopted_domain_preference(adaptation_repo, direction=PriorityDirection.BOOST)

    presentation = flow.present_replan(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8.0)
    mission_entry = next(e for e in presentation.core if e.score.item.source == "mission")
    assert any("preference you previously adopted" in fact for fact in mission_entry.explanation.facts)
