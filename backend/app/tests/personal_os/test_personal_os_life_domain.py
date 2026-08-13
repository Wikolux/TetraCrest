"""LifeDomainState (P5 §3-§6): domain activation, status transitions,
history preservation, and the persistent/seasonal/dynamic classification
model."""

from dataclasses import replace

from app.services.personal_os.life_domain import DEFAULT_CLASSIFICATION, default_state
from app.services.personal_os.life_domain_repository import InMemoryLifeDomainStateRepository
from app.services.personal_os.shared.types import LifeDomain, LifeDomainClassification, LifeDomainStatus

ORG_ID, USER_ID = 1, 1


def test_default_state_starts_not_started():
    state = default_state(LifeDomain.CAREER)
    assert state.status == LifeDomainStatus.NOT_STARTED


def test_default_classification_matches_the_users_own_stated_classification():
    """§4's own explicit table - not inferred, not configurable per
    call, the user's own words recorded as data."""
    assert DEFAULT_CLASSIFICATION[LifeDomain.CAREER] == LifeDomainClassification.SEASONAL
    assert DEFAULT_CLASSIFICATION[LifeDomain.TECHNICAL_PROJECTS] == LifeDomainClassification.SEASONAL
    assert DEFAULT_CLASSIFICATION[LifeDomain.BUSINESS] == LifeDomainClassification.PERSISTENT
    assert DEFAULT_CLASSIFICATION[LifeDomain.FINANCE_INVESTMENTS] == LifeDomainClassification.PERSISTENT
    assert DEFAULT_CLASSIFICATION[LifeDomain.PERSONAL_BRAND] == LifeDomainClassification.PERSISTENT
    assert DEFAULT_CLASSIFICATION[LifeDomain.FAMILY] == LifeDomainClassification.PERSISTENT
    assert DEFAULT_CLASSIFICATION[LifeDomain.LONG_TERM_GOALS] == LifeDomainClassification.PERSISTENT
    assert DEFAULT_CLASSIFICATION[LifeDomain.EXPERIMENTS] == LifeDomainClassification.DYNAMIC
    assert DEFAULT_CLASSIFICATION[LifeDomain.COMMITMENTS] == LifeDomainClassification.DYNAMIC


def test_every_domain_has_a_default_classification():
    for domain in LifeDomain:
        assert domain in DEFAULT_CLASSIFICATION


def test_family_state_has_no_score_or_metric_fields():
    """§22: family must never become a performance-tracking system -
    verified structurally: LifeDomainState's own field set is identical
    for every domain, and contains no score/rating/metric field at all."""
    state = default_state(LifeDomain.FAMILY)
    field_names = {f for f in state.__dataclass_fields__}
    forbidden = {"score", "rating", "health_score", "productivity", "performance"}
    assert field_names.isdisjoint(forbidden)


# --- repository: activation, transitions, history (§6) -------------------------------------------


def test_repository_returns_none_for_a_domain_never_touched():
    repo = InMemoryLifeDomainStateRepository()
    assert repo.get_latest(organization_id=ORG_ID, user_id=USER_ID, domain=LifeDomain.CAREER) is None


def test_activating_a_domain_persists_active_status():
    repo = InMemoryLifeDomainStateRepository()
    state = replace(default_state(LifeDomain.CAREER), status=LifeDomainStatus.ACTIVE, objective="Find a PM role")
    saved = repo.save(state, organization_id=ORG_ID, user_id=USER_ID)
    assert saved.status == LifeDomainStatus.ACTIVE
    assert saved.state_id != ""


def test_pausing_a_domain_preserves_the_prior_active_fact():
    """§6's own worked example: Career ACTIVE -> PAUSED must preserve
    that career activity was previously active."""
    repo = InMemoryLifeDomainStateRepository()
    active = repo.save(replace(default_state(LifeDomain.CAREER), status=LifeDomainStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(replace(active, status=LifeDomainStatus.PAUSED), organization_id=ORG_ID, user_id=USER_ID)

    history = repo.get_history(organization_id=ORG_ID, user_id=USER_ID, domain=LifeDomain.CAREER)
    assert [h.status for h in history] == [LifeDomainStatus.ACTIVE, LifeDomainStatus.PAUSED]


def test_resume_after_pause_is_historically_traceable():
    """§6's own worked example: Study ACTIVE -> PAUSED -> ACTIVE must
    remain historically traceable, not just show the current status."""
    repo = InMemoryLifeDomainStateRepository()
    active1 = repo.save(replace(default_state(LifeDomain.STUDY), status=LifeDomainStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)
    paused = repo.save(replace(active1, status=LifeDomainStatus.PAUSED), organization_id=ORG_ID, user_id=USER_ID)
    resumed = repo.save(replace(paused, status=LifeDomainStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)

    history = repo.get_history(organization_id=ORG_ID, user_id=USER_ID, domain=LifeDomain.STUDY)
    assert [h.status for h in history] == [LifeDomainStatus.ACTIVE, LifeDomainStatus.PAUSED, LifeDomainStatus.ACTIVE]
    assert repo.get_latest(organization_id=ORG_ID, user_id=USER_ID, domain=LifeDomain.STUDY).status == LifeDomainStatus.ACTIVE
    assert resumed.status == LifeDomainStatus.ACTIVE


def test_completing_a_domain_is_a_new_version_not_an_overwrite():
    repo = InMemoryLifeDomainStateRepository()
    active = repo.save(replace(default_state(LifeDomain.EXPERIMENTS), status=LifeDomainStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(replace(active, status=LifeDomainStatus.COMPLETED), organization_id=ORG_ID, user_id=USER_ID)
    history = repo.get_history(organization_id=ORG_ID, user_id=USER_ID, domain=LifeDomain.EXPERIMENTS)
    assert len(history) == 2
    assert history[0].status == LifeDomainStatus.ACTIVE


def test_list_all_latest_only_includes_touched_domains():
    """Seasonal/dynamic domains never touched must not appear as if
    fabricated ACTIVE state (§4's own "do not hard-code these domains as
    permanently active")."""
    repo = InMemoryLifeDomainStateRepository()
    repo.save(replace(default_state(LifeDomain.CAREER), status=LifeDomainStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)

    latest = repo.list_all_latest(organization_id=ORG_ID, user_id=USER_ID)
    assert len(latest) == 1
    assert latest[0].domain == LifeDomain.CAREER


def test_repository_scopes_by_organization_and_user():
    repo = InMemoryLifeDomainStateRepository()
    repo.save(replace(default_state(LifeDomain.CAREER), status=LifeDomainStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(replace(default_state(LifeDomain.CAREER), status=LifeDomainStatus.ACTIVE), organization_id=ORG_ID, user_id=99)

    assert len(repo.list_all_latest(organization_id=ORG_ID, user_id=USER_ID)) == 1


def test_seasonal_domain_can_be_activated_then_paused_after_the_season_ends():
    """§4's own worked example: Career can be activated while job
    hunting and paused after obtaining a job."""
    repo = InMemoryLifeDomainStateRepository()
    hunting = replace(default_state(LifeDomain.CAREER), status=LifeDomainStatus.ACTIVE, objective="Land a PM role")
    repo.save(hunting, organization_id=ORG_ID, user_id=USER_ID)
    got_the_job = repo.save(replace(hunting, status=LifeDomainStatus.PAUSED, objective="Job secured - resume if needed"), organization_id=ORG_ID, user_id=USER_ID)
    assert got_the_job.status == LifeDomainStatus.PAUSED
    assert got_the_job.classification == LifeDomainClassification.SEASONAL
