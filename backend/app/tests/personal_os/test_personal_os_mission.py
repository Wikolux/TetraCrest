"""Mission (P5 §14-§17): creation, lifecycle transitions, history
preservation, constraints/budget/preferences, and the nested
AutonomyGrant shape."""

from dataclasses import replace

import pytest

from app.services.personal_os.mission import AutonomyGrant, Mission
from app.services.personal_os.mission_repository import InMemoryMissionRepository
from app.services.personal_os.shared.types import AutonomyAction, LifeDomain, MissionStatus

ORG_ID, USER_ID = 1, 6


def _mission(mission_id="", status=MissionStatus.DRAFT, **kwargs):
    return Mission(mission_id=mission_id, objective="Plan a surprise vacation for my wife", status=status, **kwargs)


def test_mission_requires_an_objective():
    with pytest.raises(ValueError):
        Mission(mission_id="", objective="")


def test_mission_starts_in_draft_by_default():
    mission = _mission()
    assert mission.status == MissionStatus.DRAFT


def test_mission_carries_constraints_budget_and_preferences():
    mission = _mission(budget="₦500,000", constraints=("dates: 10-20 Dec",), preferences=("beach", "relaxing", "surprise"))
    assert mission.budget == "₦500,000"
    assert mission.constraints == ("dates: 10-20 Dec",)
    assert mission.preferences == ("beach", "relaxing", "surprise")


def test_mission_can_carry_a_related_domain_and_next_step():
    mission = _mission(domain=LifeDomain.FAMILY, next_step="Research beach destinations")
    assert mission.domain == LifeDomain.FAMILY
    assert mission.next_step == "Research beach destinations"


def test_autonomy_grant_requires_a_scope():
    with pytest.raises(ValueError):
        AutonomyGrant(action=AutonomyAction.RESEARCH, scope="")


def test_mission_carries_autonomy_grants():
    grant = AutonomyGrant(action=AutonomyAction.RESEARCH, scope="Destination and flight research")
    mission = _mission(autonomy_grants=(grant,))
    assert mission.autonomy_grants == (grant,)


# --- repository: create, activate, pause, complete, cancel, history (§15) -------------------------


def test_create_assigns_a_mission_id():
    repo = InMemoryMissionRepository()
    saved = repo.save(_mission(), organization_id=ORG_ID, user_id=USER_ID)
    assert saved.mission_id != ""


def test_activate_transitions_from_draft():
    repo = InMemoryMissionRepository()
    draft = repo.save(_mission(status=MissionStatus.DRAFT), organization_id=ORG_ID, user_id=USER_ID)
    activated = repo.save(replace(draft, status=MissionStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)
    assert activated.status == MissionStatus.ACTIVE


def test_pause_and_resume_preserve_history():
    repo = InMemoryMissionRepository()
    active = repo.save(_mission(status=MissionStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)
    paused = repo.save(replace(active, status=MissionStatus.PAUSED), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(replace(paused, status=MissionStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)

    history = repo.get_history(organization_id=ORG_ID, user_id=USER_ID, mission_id=active.mission_id)
    assert [h.status for h in history] == [MissionStatus.ACTIVE, MissionStatus.PAUSED, MissionStatus.ACTIVE]


def test_complete_is_a_new_version_never_an_overwrite():
    repo = InMemoryMissionRepository()
    active = repo.save(_mission(status=MissionStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(replace(active, status=MissionStatus.COMPLETED), organization_id=ORG_ID, user_id=USER_ID)
    history = repo.get_history(organization_id=ORG_ID, user_id=USER_ID, mission_id=active.mission_id)
    assert len(history) == 2
    assert history[0].status == MissionStatus.ACTIVE


def test_cancel_is_distinguishable_from_complete():
    repo = InMemoryMissionRepository()
    active = repo.save(_mission(status=MissionStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)
    cancelled = repo.save(replace(active, status=MissionStatus.CANCELLED), organization_id=ORG_ID, user_id=USER_ID)
    assert cancelled.status != MissionStatus.COMPLETED
    assert cancelled.status == MissionStatus.CANCELLED


def test_list_active_excludes_completed_and_cancelled():
    repo = InMemoryMissionRepository()
    repo.save(_mission(status=MissionStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_mission(status=MissionStatus.COMPLETED), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_mission(status=MissionStatus.CANCELLED), organization_id=ORG_ID, user_id=USER_ID)

    active = repo.list_active(organization_id=ORG_ID, user_id=USER_ID)
    assert len(active) == 1
    assert active[0].status == MissionStatus.ACTIVE


def test_list_active_includes_draft_and_paused():
    repo = InMemoryMissionRepository()
    repo.save(_mission(status=MissionStatus.DRAFT), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_mission(status=MissionStatus.PAUSED), organization_id=ORG_ID, user_id=USER_ID)

    active = repo.list_active(organization_id=ORG_ID, user_id=USER_ID)
    assert len(active) == 2


def test_repository_scopes_by_organization_and_user():
    repo = InMemoryMissionRepository()
    repo.save(_mission(status=MissionStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_mission(status=MissionStatus.ACTIVE), organization_id=ORG_ID, user_id=99)

    assert len(repo.list_active(organization_id=ORG_ID, user_id=USER_ID)) == 1


def test_target_date_is_preserved():
    from datetime import date

    repo = InMemoryMissionRepository()
    saved = repo.save(_mission(target_date=date(2026, 12, 20)), organization_id=ORG_ID, user_id=USER_ID)
    assert saved.target_date == date(2026, 12, 20)
