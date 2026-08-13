"""PriorityIntelligenceFlow (P5 §13, §25-§27): asking day mode before
planning, gathering candidates from every connected source, presenting a
ranked Core 5 + Optional 2 with explanations, and applying a hold
override without deleting anything."""

from datetime import date

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.runtime.types import RuntimeResponse
from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.experiment_repository import InMemoryExperimentRepository
from app.services.personal_os.mission import Mission
from app.services.personal_os.mission_repository import InMemoryMissionRepository
from app.services.personal_os.pattern_repository import InMemoryPatternRepository
from app.services.personal_os.priority_flow import PriorityIntelligenceFlow
from app.services.personal_os.repository import InMemoryDailyIntentRepository
from app.services.personal_os.shared.types import DayModeKind, DayType, LifeDomain, MissionStatus

ORG_ID, USER_ID = 1, 8
TODAY = date(2026, 8, 13)


class _FakeRuntime:
    """Mirrors every other Personal OS flow's own fake runtime - returns
    success=False so tests exercise the honest, deterministic fallback."""

    def __init__(self):
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return RuntimeResponse(success=False)


def _flow():
    intent_repo = InMemoryDailyIntentRepository()
    mission_repo = InMemoryMissionRepository()
    pattern_repo = InMemoryPatternRepository()
    experiment_repo = InMemoryExperimentRepository()
    flow = PriorityIntelligenceFlow(intent_repo, mission_repo, pattern_repo, experiment_repo, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()))
    return flow, intent_repo, mission_repo, pattern_repo, experiment_repo


# --- ask before planning (§11, §13) --------------------------------------------------------------


def test_ask_day_mode_asks_before_generating_a_ranking():
    flow, *_ = _flow()
    assert flow.ask_day_mode() == "Good morning. What kind of day are we having?"


def test_resolve_day_mode_recognizes_a_known_keyword():
    flow, *_ = _flow()
    mode = flow.resolve_day_mode("I want a focused workday")
    assert mode.kind == DayModeKind.STRUCTURED_PRODUCTIVE


def test_resolve_day_mode_preserves_an_unrecognized_statement_as_custom():
    flow, *_ = _flow()
    mode = flow.resolve_day_mode("A slow, creative kind of day")
    assert mode.kind == DayModeKind.CUSTOM
    assert mode.custom_label == "A slow, creative kind of day"


# --- candidate gathering connects to every source without duplicating them (§26) -----------------


def test_gather_candidates_includes_todays_planned_activities():
    flow, intent_repo, *_ = _flow()
    intent = DailyIntent(intent_date=TODAY, stated_intention="x", day_type=DayType.MIXED, planned_activities=(PlannedActivity(description="Ship the report"),))
    intent_repo.save(intent, organization_id=ORG_ID, user_id=USER_ID)

    candidates = flow.gather_candidates(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    assert any(c.description == "Ship the report" for c in candidates)


def test_gather_candidates_includes_active_mission_next_steps():
    flow, _, mission_repo, *_ = _flow()
    mission_repo.save(Mission(mission_id="", objective="Find a PM role", status=MissionStatus.ACTIVE, next_step="Follow up with recruiter"), organization_id=ORG_ID, user_id=USER_ID)

    candidates = flow.gather_candidates(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    assert any(c.description == "Follow up with recruiter" for c in candidates)


def test_gather_candidates_handles_no_intent_recorded_yet():
    flow, *_ = _flow()
    candidates = flow.gather_candidates(organization_id=ORG_ID, user_id=USER_ID, today=TODAY)
    assert candidates == ()


# --- ranking and presentation (§10, §12) -----------------------------------------------------------


def test_build_ranking_produces_core_and_optional():
    flow, intent_repo, mission_repo, *_ = _flow()
    intent = DailyIntent(
        intent_date=TODAY, stated_intention="x", day_type=DayType.MIXED,
        planned_activities=(PlannedActivity(description="Job application", focus_area="career", deadline=TODAY),),
    )
    intent_repo.save(intent, organization_id=ORG_ID, user_id=USER_ID)
    mission_repo.save(Mission(mission_id="", objective="x", status=MissionStatus.ACTIVE, next_step="Follow up"), organization_id=ORG_ID, user_id=USER_ID)

    ranking = flow.build_ranking(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8)
    assert len(ranking.core) == 2


def test_present_produces_a_narrative_and_explanation_per_entry():
    flow, intent_repo, *_ = _flow()
    intent = DailyIntent(intent_date=TODAY, stated_intention="x", day_type=DayType.MIXED, planned_activities=(PlannedActivity(description="Ship the report", deadline=TODAY),))
    intent_repo.save(intent, organization_id=ORG_ID, user_id=USER_ID)

    ranking = flow.build_ranking(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8)
    presentation = flow.present(ranking, organization_id=ORG_ID, today=TODAY)
    assert len(presentation.core) == 1
    assert presentation.core[0].narrative
    assert presentation.core[0].explanation.facts
    assert presentation.closing_question == "Anything else you want to add or remove?"


# --- hold override adapts without deleting (§13, §21, §30) -----------------------------------------


def test_apply_hold_adapts_to_family_day_without_deleting_commitments():
    flow, intent_repo, mission_repo, *_ = _flow()
    intent = DailyIntent(
        intent_date=TODAY, stated_intention="x", day_type=DayType.MIXED,
        planned_activities=(PlannedActivity(description="Job application", focus_area="career", deadline=TODAY),),
    )
    intent_repo.save(intent, organization_id=ORG_ID, user_id=USER_ID)
    mission_repo.save(Mission(mission_id="", objective="x", status=MissionStatus.ACTIVE, domain=LifeDomain.CAREER, next_step="Follow up with recruiter"), organization_id=ORG_ID, user_id=USER_ID)

    result = flow.apply_hold(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8, day_mode=None, hold_domains=(LifeDomain.CAREER,))

    # the non-urgent mission next-step is held (safe to move), never deleted
    assert any(item.description == "Follow up with recruiter" for item in result.held_items)
    # the urgent, deadline-today job application is still surfaced
    assert any(s.item.description == "Job application" for s in result.surfaced_despite_hold)
    # nothing was removed from the underlying repositories
    assert mission_repo.list_active(organization_id=ORG_ID, user_id=USER_ID)[0].next_step == "Follow up with recruiter"
