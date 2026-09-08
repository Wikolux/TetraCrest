"""PriorityIntelligenceFlow (P5 §13, §25-§27): asking day mode before
planning, gathering candidates from every connected source, presenting a
ranked Core 5 + Optional 2 with explanations, and applying a hold
override without deleting anything."""

from datetime import date

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.runtime.types import RuntimeResponse
from app.services.personal_os.adaptation import Adaptation, AdaptationEffect, AdaptationTarget
from app.services.personal_os.adaptation_repository import InMemoryAdaptationRepository
from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.experiment_repository import InMemoryExperimentRepository
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
    DayModeKind,
    DayType,
    LifeDomain,
    MissionStatus,
    PriorityDirection,
)

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


def _flow(adaptation_repository=None):
    intent_repo = InMemoryDailyIntentRepository()
    mission_repo = InMemoryMissionRepository()
    pattern_repo = InMemoryPatternRepository()
    experiment_repo = InMemoryExperimentRepository()
    flow = PriorityIntelligenceFlow(
        intent_repo,
        mission_repo,
        pattern_repo,
        experiment_repo,
        runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()),
        adaptation_repository=adaptation_repository,
    )
    return flow, intent_repo, mission_repo, pattern_repo, experiment_repo


def _adopted(adaptation_repo, *, organization_id, user_id, scope, target_id, direction, supersedes_id=None):
    """Seeds an already-ADOPTED adaptation directly in the repository -
    the lifecycle transitions themselves are AdaptationFlow's own,
    already fully covered by test_personal_os_adaptation_flow.py; these
    tests exist to prove the Priority Engine consumes whatever the
    repository currently reports as adopted, not to re-test adoption."""
    target = AdaptationTarget(scope=scope, target_id=target_id)
    effect = AdaptationEffect(kind=AdaptationEffectKind.PRIORITY_ADJUSTMENT, direction=direction)
    adaptation = Adaptation(
        adaptation_id="",
        target=target,
        pattern_id="pattern-1",
        confidence=Confidence.MEDIUM,
        status=AdaptationStatus.ADOPTED,
        effect=effect,
        supersedes_adaptation_id=supersedes_id,
    )
    return adaptation_repo.save(adaptation, organization_id=organization_id, user_id=user_id)


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


# --- P7.11: adopted adaptations influence candidate construction, never the deterministic core -----


def _mission_flow(adaptation_repo=None, *, domain=LifeDomain.CAREER, mission_id="m1"):
    flow, intent_repo, mission_repo, *_ = _flow(adaptation_repo)
    mission_repo.save(
        Mission(mission_id=mission_id, objective="x", status=MissionStatus.ACTIVE, domain=domain, next_step="Follow up with recruiter"),
        organization_id=ORG_ID,
        user_id=USER_ID,
    )
    return flow, intent_repo, mission_repo


def test_no_adaptation_repository_matches_p6_p7_10_behavior_exactly():
    """§16 hard regression requirement: omitting adaptation_repository
    entirely (every P6/P7.10 construction site) must be byte-for-byte
    identical to a repository that simply has nothing adopted."""
    flow_without, *_ = _mission_flow(None)
    flow_with, *_ = _mission_flow(InMemoryAdaptationRepository())

    without = flow_without.gather_non_intent_candidates(organization_id=ORG_ID, user_id=USER_ID)
    with_empty_repo = flow_with.gather_non_intent_candidates(organization_id=ORG_ID, user_id=USER_ID)
    assert without == with_empty_repo


def test_adopted_user_preference_boosts_momentum_of_matching_mission_candidate():
    adaptation_repo = InMemoryAdaptationRepository()
    flow, *_ = _mission_flow(adaptation_repo, domain=LifeDomain.CAREER)
    _adopted(adaptation_repo, organization_id=ORG_ID, user_id=USER_ID, scope=AdaptationScope.USER_PREFERENCE, target_id=LifeDomain.CAREER.value, direction=PriorityDirection.BOOST)

    candidates = flow.gather_non_intent_candidates(organization_id=ORG_ID, user_id=USER_ID)
    mission_candidate = next(c for c in candidates if c.source == "mission")
    assert mission_candidate.momentum == flow.config.adaptation_priority_boost


def test_adopted_mission_scoped_effect_boosts_only_that_mission():
    adaptation_repo = InMemoryAdaptationRepository()
    flow, intent_repo, mission_repo = _mission_flow(adaptation_repo, domain=LifeDomain.CAREER, mission_id="m1")
    mission_repo.save(Mission(mission_id="m2", objective="y", status=MissionStatus.ACTIVE, domain=LifeDomain.CAREER, next_step="Other next step"), organization_id=ORG_ID, user_id=USER_ID)
    _adopted(adaptation_repo, organization_id=ORG_ID, user_id=USER_ID, scope=AdaptationScope.MISSION, target_id="m1", direction=PriorityDirection.BOOST)

    candidates = flow.gather_non_intent_candidates(organization_id=ORG_ID, user_id=USER_ID)
    by_id = {c.source_id: c for c in candidates if c.source == "mission"}
    assert by_id["m1"].momentum == flow.config.adaptation_priority_boost
    assert by_id["m2"].momentum == 0.0


def test_a_merely_approved_not_adopted_adaptation_has_no_runtime_effect():
    """Approval boundary (§20): PROPOSED/APPROVED must never leak into
    behavior - only ADOPTED does."""
    adaptation_repo = InMemoryAdaptationRepository()
    flow, *_ = _mission_flow(adaptation_repo, domain=LifeDomain.CAREER)
    _adopted(adaptation_repo, organization_id=ORG_ID, user_id=USER_ID, scope=AdaptationScope.USER_PREFERENCE, target_id=LifeDomain.CAREER.value, direction=PriorityDirection.BOOST)
    # overwrite with an APPROVED (not yet adopted) version of the same adaptation_id
    latest = adaptation_repo.list_active(organization_id=ORG_ID, user_id=USER_ID)[0]
    from dataclasses import replace as _replace

    adaptation_repo.save(_replace(latest, status=AdaptationStatus.APPROVED), organization_id=ORG_ID, user_id=USER_ID)

    candidates = flow.gather_non_intent_candidates(organization_id=ORG_ID, user_id=USER_ID)
    mission_candidate = next(c for c in candidates if c.source == "mission")
    assert mission_candidate.momentum == 0.0


def test_explicit_current_intent_outranks_an_adopted_preference_boost():
    """§10/§12: today's explicit statement must win over a learned
    preference, proven through the real ranking math, not asserted."""
    adaptation_repo = InMemoryAdaptationRepository()
    flow, intent_repo, mission_repo = _mission_flow(adaptation_repo, domain=LifeDomain.CAREER)
    intent = DailyIntent(intent_date=TODAY, stated_intention="Clear all admin work first", day_type=DayType.MIXED, planned_activities=(PlannedActivity(description="Clear admin inbox"),))
    intent_repo.save(intent, organization_id=ORG_ID, user_id=USER_ID)
    _adopted(adaptation_repo, organization_id=ORG_ID, user_id=USER_ID, scope=AdaptationScope.USER_PREFERENCE, target_id=LifeDomain.CAREER.value, direction=PriorityDirection.BOOST)

    ranking = flow.build_ranking(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8)
    assert ranking.core[0].item.description == "Clear admin inbox"


def test_user_isolation_one_users_adopted_adaptation_never_affects_another():
    adaptation_repo = InMemoryAdaptationRepository()
    flow, *_ = _mission_flow(adaptation_repo, domain=LifeDomain.CAREER)
    other_user_id = USER_ID + 1
    _adopted(adaptation_repo, organization_id=ORG_ID, user_id=other_user_id, scope=AdaptationScope.USER_PREFERENCE, target_id=LifeDomain.CAREER.value, direction=PriorityDirection.BOOST)

    candidates = flow.gather_non_intent_candidates(organization_id=ORG_ID, user_id=USER_ID)
    mission_candidate = next(c for c in candidates if c.source == "mission")
    assert mission_candidate.momentum == 0.0


def test_organization_isolation_one_orgs_adopted_adaptation_never_affects_another():
    adaptation_repo = InMemoryAdaptationRepository()
    flow, *_ = _mission_flow(adaptation_repo, domain=LifeDomain.CAREER)
    other_org_id = ORG_ID + 1
    _adopted(adaptation_repo, organization_id=other_org_id, user_id=USER_ID, scope=AdaptationScope.USER_PREFERENCE, target_id=LifeDomain.CAREER.value, direction=PriorityDirection.BOOST)

    candidates = flow.gather_non_intent_candidates(organization_id=ORG_ID, user_id=USER_ID)
    mission_candidate = next(c for c in candidates if c.source == "mission")
    assert mission_candidate.momentum == 0.0


def test_mission_isolation_one_missions_adopted_effect_never_affects_another():
    adaptation_repo = InMemoryAdaptationRepository()
    flow, intent_repo, mission_repo = _mission_flow(adaptation_repo, domain=LifeDomain.CAREER, mission_id="m1")
    mission_repo.save(Mission(mission_id="m2", objective="y", status=MissionStatus.ACTIVE, domain=LifeDomain.STUDY, next_step="Other next step"), organization_id=ORG_ID, user_id=USER_ID)
    _adopted(adaptation_repo, organization_id=ORG_ID, user_id=USER_ID, scope=AdaptationScope.MISSION, target_id="m1", direction=PriorityDirection.BOOST)

    candidates = flow.gather_non_intent_candidates(organization_id=ORG_ID, user_id=USER_ID)
    by_id = {c.source_id: c for c in candidates if c.source == "mission"}
    assert by_id["m2"].momentum == 0.0


def test_rollback_restores_baseline_behavior():
    adaptation_repo = InMemoryAdaptationRepository()
    flow, *_ = _mission_flow(adaptation_repo, domain=LifeDomain.CAREER)
    adopted = _adopted(adaptation_repo, organization_id=ORG_ID, user_id=USER_ID, scope=AdaptationScope.USER_PREFERENCE, target_id=LifeDomain.CAREER.value, direction=PriorityDirection.BOOST)

    boosted = flow.gather_non_intent_candidates(organization_id=ORG_ID, user_id=USER_ID)
    assert next(c for c in boosted if c.source == "mission").momentum == flow.config.adaptation_priority_boost

    from dataclasses import replace as _replace

    adaptation_repo.save(_replace(adopted, status=AdaptationStatus.ROLLED_BACK), organization_id=ORG_ID, user_id=USER_ID)

    restored = flow.gather_non_intent_candidates(organization_id=ORG_ID, user_id=USER_ID)
    assert next(c for c in restored if c.source == "mission").momentum == 0.0


def test_supersession_only_the_current_adopted_replacement_affects_behavior():
    adaptation_repo = InMemoryAdaptationRepository()
    flow, *_ = _mission_flow(adaptation_repo, domain=LifeDomain.CAREER)
    original = _adopted(adaptation_repo, organization_id=ORG_ID, user_id=USER_ID, scope=AdaptationScope.USER_PREFERENCE, target_id=LifeDomain.CAREER.value, direction=PriorityDirection.BOOST)

    from dataclasses import replace as _replace

    adaptation_repo.save(_replace(original, status=AdaptationStatus.SUPERSEDED), organization_id=ORG_ID, user_id=USER_ID)
    _adopted(
        adaptation_repo,
        organization_id=ORG_ID,
        user_id=USER_ID,
        scope=AdaptationScope.USER_PREFERENCE,
        target_id=LifeDomain.CAREER.value,
        direction=PriorityDirection.SUPPRESS,
        supersedes_id=original.adaptation_id,
    )

    candidates = flow.gather_non_intent_candidates(organization_id=ORG_ID, user_id=USER_ID)
    mission_candidate = next(c for c in candidates if c.source == "mission")
    assert mission_candidate.momentum == 0.0  # suppressed from a 0.0 baseline, clamped at the floor


def test_unsupported_scopes_are_never_read_for_runtime_effects():
    """§8/§22: USER and WORKFLOW remain deferred for this milestone - an
    adopted adaptation under either scope must never invent behavior."""
    adaptation_repo = InMemoryAdaptationRepository()
    flow, *_ = _mission_flow(adaptation_repo, domain=LifeDomain.CAREER)
    _adopted(adaptation_repo, organization_id=ORG_ID, user_id=USER_ID, scope=AdaptationScope.USER, target_id=str(USER_ID), direction=PriorityDirection.BOOST)
    _adopted(adaptation_repo, organization_id=ORG_ID, user_id=USER_ID, scope=AdaptationScope.WORKFLOW, target_id="morning_flow", direction=PriorityDirection.BOOST)

    candidates = flow.gather_non_intent_candidates(organization_id=ORG_ID, user_id=USER_ID)
    mission_candidate = next(c for c in candidates if c.source == "mission")
    assert mission_candidate.momentum == 0.0


def test_present_attributes_a_boosted_ranking_to_the_adopted_preference():
    adaptation_repo = InMemoryAdaptationRepository()
    flow, *_ = _mission_flow(adaptation_repo, domain=LifeDomain.CAREER)
    _adopted(adaptation_repo, organization_id=ORG_ID, user_id=USER_ID, scope=AdaptationScope.USER_PREFERENCE, target_id=LifeDomain.CAREER.value, direction=PriorityDirection.BOOST)

    ranking = flow.build_ranking(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8)
    presentation = flow.present(ranking, organization_id=ORG_ID, today=TODAY, user_id=USER_ID)
    mission_entry = next(e for e in presentation.core if e.score.item.source == "mission")
    assert any("preference you previously adopted" in fact for fact in mission_entry.explanation.facts)


def test_present_without_user_id_omits_attribution_but_still_works():
    """Backward compatibility: every existing caller of present() that
    does not pass user_id must be entirely unaffected."""
    adaptation_repo = InMemoryAdaptationRepository()
    flow, *_ = _mission_flow(adaptation_repo, domain=LifeDomain.CAREER)
    _adopted(adaptation_repo, organization_id=ORG_ID, user_id=USER_ID, scope=AdaptationScope.USER_PREFERENCE, target_id=LifeDomain.CAREER.value, direction=PriorityDirection.BOOST)

    ranking = flow.build_ranking(organization_id=ORG_ID, user_id=USER_ID, today=TODAY, available_hours=8)
    presentation = flow.present(ranking, organization_id=ORG_ID, today=TODAY)
    mission_entry = next(e for e in presentation.core if e.score.item.source == "mission")
    assert not any("preference you previously adopted" in fact for fact in mission_entry.explanation.facts)
