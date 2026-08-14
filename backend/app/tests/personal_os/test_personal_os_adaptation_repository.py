"""InMemoryAdaptationRepository (P7.10): append-only version history,
scope isolation, and the get_adopted_for_target() query surface - the
same contract SqlAdaptationRepository (tested separately, against a real
database, in test_personal_os_sql_repository.py) must also satisfy."""

from dataclasses import replace

from app.services.personal_os.adaptation import Adaptation, AdaptationTarget
from app.services.personal_os.adaptation_repository import InMemoryAdaptationRepository
from app.services.personal_os.shared.types import AdaptationScope, AdaptationStatus, Confidence

ORG_ID, USER_ID = 1, 11


def _adaptation(adaptation_id="", scope=AdaptationScope.USER, target_id="1", status=AdaptationStatus.PROPOSED, **kwargs):
    target = AdaptationTarget(scope=scope, target_id=target_id)
    return Adaptation(adaptation_id=adaptation_id, target=target, pattern_id="p1", confidence=Confidence.MEDIUM, status=status, **kwargs)


def test_save_assigns_an_adaptation_id():
    repo = InMemoryAdaptationRepository()
    saved = repo.save(_adaptation(), organization_id=ORG_ID, user_id=USER_ID)
    assert saved.adaptation_id != ""


def test_get_latest_returns_none_when_nothing_saved():
    repo = InMemoryAdaptationRepository()
    assert repo.get_latest(organization_id=ORG_ID, user_id=USER_ID, adaptation_id="does-not-exist") is None


def test_get_latest_returns_the_most_recent_version():
    repo = InMemoryAdaptationRepository()
    first = repo.save(_adaptation(status=AdaptationStatus.PROPOSED), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(replace(first, status=AdaptationStatus.UNDER_EVALUATION), organization_id=ORG_ID, user_id=USER_ID)

    latest = repo.get_latest(organization_id=ORG_ID, user_id=USER_ID, adaptation_id=first.adaptation_id)
    assert latest.status == AdaptationStatus.UNDER_EVALUATION


def test_get_history_returns_every_version_in_order():
    repo = InMemoryAdaptationRepository()
    first = repo.save(_adaptation(status=AdaptationStatus.PROPOSED), organization_id=ORG_ID, user_id=USER_ID)
    second = repo.save(replace(first, status=AdaptationStatus.UNDER_EVALUATION), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(replace(second, status=AdaptationStatus.APPROVED), organization_id=ORG_ID, user_id=USER_ID)

    history = repo.get_history(organization_id=ORG_ID, user_id=USER_ID, adaptation_id=first.adaptation_id)
    assert [h.status for h in history] == [AdaptationStatus.PROPOSED, AdaptationStatus.UNDER_EVALUATION, AdaptationStatus.APPROVED]


def test_list_active_excludes_terminal_statuses():
    repo = InMemoryAdaptationRepository()
    repo.save(_adaptation(status=AdaptationStatus.PROPOSED), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_adaptation(status=AdaptationStatus.REJECTED), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_adaptation(status=AdaptationStatus.ROLLED_BACK), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_adaptation(status=AdaptationStatus.SUPERSEDED), organization_id=ORG_ID, user_id=USER_ID)

    active = repo.list_active(organization_id=ORG_ID, user_id=USER_ID)
    assert len(active) == 1
    assert active[0].status == AdaptationStatus.PROPOSED


def test_list_active_includes_adopted():
    repo = InMemoryAdaptationRepository()
    repo.save(_adaptation(status=AdaptationStatus.ADOPTED), organization_id=ORG_ID, user_id=USER_ID)
    active = repo.list_active(organization_id=ORG_ID, user_id=USER_ID)
    assert len(active) == 1


def test_get_adopted_for_target_finds_the_right_one():
    repo = InMemoryAdaptationRepository()
    target = AdaptationTarget(scope=AdaptationScope.MISSION, target_id="mission-1")
    repo.save(_adaptation(scope=AdaptationScope.MISSION, target_id="mission-1", status=AdaptationStatus.ADOPTED), organization_id=ORG_ID, user_id=USER_ID)

    adopted = repo.get_adopted_for_target(organization_id=ORG_ID, user_id=USER_ID, target=target)
    assert adopted is not None
    assert adopted.status == AdaptationStatus.ADOPTED


def test_get_adopted_for_target_returns_none_when_not_adopted():
    repo = InMemoryAdaptationRepository()
    target = AdaptationTarget(scope=AdaptationScope.MISSION, target_id="mission-1")
    repo.save(_adaptation(scope=AdaptationScope.MISSION, target_id="mission-1", status=AdaptationStatus.PROPOSED), organization_id=ORG_ID, user_id=USER_ID)

    assert repo.get_adopted_for_target(organization_id=ORG_ID, user_id=USER_ID, target=target) is None


# --- scope isolation (§9) ---------------------------------------------------------------------------


def test_get_adopted_for_target_never_leaks_across_different_targets_in_the_same_scope():
    """MISSION adaptation for mission-1 must never be returned as
    adopted for mission-2."""
    repo = InMemoryAdaptationRepository()
    repo.save(_adaptation(scope=AdaptationScope.MISSION, target_id="mission-1", status=AdaptationStatus.ADOPTED), organization_id=ORG_ID, user_id=USER_ID)

    other_target = AdaptationTarget(scope=AdaptationScope.MISSION, target_id="mission-2")
    assert repo.get_adopted_for_target(organization_id=ORG_ID, user_id=USER_ID, target=other_target) is None


def test_get_adopted_for_target_never_leaks_across_scopes_with_the_same_target_id():
    """A USER_PREFERENCE adaptation for target_id '1' must never be
    returned when querying MISSION scope with the same target_id."""
    repo = InMemoryAdaptationRepository()
    repo.save(_adaptation(scope=AdaptationScope.USER_PREFERENCE, target_id="1", status=AdaptationStatus.ADOPTED), organization_id=ORG_ID, user_id=USER_ID)

    mission_target = AdaptationTarget(scope=AdaptationScope.MISSION, target_id="1")
    assert repo.get_adopted_for_target(organization_id=ORG_ID, user_id=USER_ID, target=mission_target) is None


def test_repository_scopes_by_organization_and_user():
    repo = InMemoryAdaptationRepository()
    repo.save(_adaptation(status=AdaptationStatus.ADOPTED), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_adaptation(status=AdaptationStatus.ADOPTED), organization_id=ORG_ID, user_id=99)

    assert len(repo.list_active(organization_id=ORG_ID, user_id=USER_ID)) == 1
