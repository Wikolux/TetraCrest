"""InMemoryExperimentRepository (P4 §16): append-only, per-experiment-id
version history - the same contract SqlExperimentRepository (tested
separately, against a real database, in test_personal_os_sql_repository
.py) must also satisfy."""

from datetime import date

from app.services.personal_os.experiment import Experiment, ExperimentBaseline
from app.services.personal_os.experiment_repository import InMemoryExperimentRepository
from app.services.personal_os.shared.types import ExperimentStatus

ORG_ID, USER_ID = 1, 4


def _experiment(experiment_id="", status=ExperimentStatus.PROPOSED, review_date=date(2026, 7, 30)):
    baseline = ExperimentBaseline(
        metric="postponement_count", category="learning", period_start=date(2026, 7, 1), period_end=date(2026, 7, 14), value=4.0, observation_count=4
    )
    return Experiment(
        experiment_id=experiment_id,
        pattern_id="pattern-1",
        hypothesis_statement="h",
        adjustment="a",
        measurement_plan="m",
        baseline=baseline,
        started_on=date(2026, 7, 16),
        review_date=review_date,
        status=status,
    )


def test_save_assigns_an_experiment_id_when_none_is_given():
    repo = InMemoryExperimentRepository()
    saved = repo.save(_experiment(), organization_id=ORG_ID, user_id=USER_ID)
    assert saved.experiment_id != ""


def test_get_latest_returns_none_when_nothing_saved():
    repo = InMemoryExperimentRepository()
    assert repo.get_latest(organization_id=ORG_ID, user_id=USER_ID, experiment_id="does-not-exist") is None


def test_get_latest_returns_the_most_recently_saved_version():
    repo = InMemoryExperimentRepository()
    from dataclasses import replace

    first = repo.save(_experiment(status=ExperimentStatus.PROPOSED), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(replace(first, status=ExperimentStatus.APPROVED), organization_id=ORG_ID, user_id=USER_ID)

    latest = repo.get_latest(organization_id=ORG_ID, user_id=USER_ID, experiment_id=first.experiment_id)
    assert latest.status == ExperimentStatus.APPROVED


def test_get_history_returns_every_version_in_order():
    repo = InMemoryExperimentRepository()
    from dataclasses import replace

    first = repo.save(_experiment(status=ExperimentStatus.PROPOSED), organization_id=ORG_ID, user_id=USER_ID)
    second = repo.save(replace(first, status=ExperimentStatus.APPROVED), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(replace(second, status=ExperimentStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)

    history = repo.get_history(organization_id=ORG_ID, user_id=USER_ID, experiment_id=first.experiment_id)
    assert [h.status for h in history] == [ExperimentStatus.PROPOSED, ExperimentStatus.APPROVED, ExperimentStatus.ACTIVE]


def test_list_active_excludes_terminal_statuses():
    repo = InMemoryExperimentRepository()
    repo.save(_experiment(status=ExperimentStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_experiment(status=ExperimentStatus.KEPT), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_experiment(status=ExperimentStatus.STOPPED), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_experiment(status=ExperimentStatus.EXPIRED), organization_id=ORG_ID, user_id=USER_ID)

    active = repo.list_active(organization_id=ORG_ID, user_id=USER_ID)
    assert len(active) == 1
    assert active[0].status == ExperimentStatus.ACTIVE


def test_list_active_scopes_by_organization_and_user():
    repo = InMemoryExperimentRepository()
    repo.save(_experiment(status=ExperimentStatus.ACTIVE), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_experiment(status=ExperimentStatus.ACTIVE), organization_id=ORG_ID, user_id=99)

    active = repo.list_active(organization_id=ORG_ID, user_id=USER_ID)
    assert len(active) == 1


def test_list_ready_for_review_includes_active_experiments_past_their_review_date():
    repo = InMemoryExperimentRepository()
    repo.save(_experiment(status=ExperimentStatus.ACTIVE, review_date=date(2026, 7, 30)), organization_id=ORG_ID, user_id=USER_ID)

    not_yet = repo.list_ready_for_review(organization_id=ORG_ID, user_id=USER_ID, today=date(2026, 7, 20))
    assert not_yet == ()

    ready = repo.list_ready_for_review(organization_id=ORG_ID, user_id=USER_ID, today=date(2026, 7, 30))
    assert len(ready) == 1


def test_list_ready_for_review_includes_experiments_already_marked_ready():
    repo = InMemoryExperimentRepository()
    repo.save(_experiment(status=ExperimentStatus.READY_FOR_REVIEW, review_date=date(2026, 7, 30)), organization_id=ORG_ID, user_id=USER_ID)

    ready = repo.list_ready_for_review(organization_id=ORG_ID, user_id=USER_ID, today=date(2026, 7, 1))
    assert len(ready) == 1


def test_list_ready_for_review_excludes_active_experiments_without_a_review_date():
    repo = InMemoryExperimentRepository()
    repo.save(_experiment(status=ExperimentStatus.ACTIVE, review_date=None), organization_id=ORG_ID, user_id=USER_ID)

    ready = repo.list_ready_for_review(organization_id=ORG_ID, user_id=USER_ID, today=date(2026, 12, 31))
    assert ready == ()
