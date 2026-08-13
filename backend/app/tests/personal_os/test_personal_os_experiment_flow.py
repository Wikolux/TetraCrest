"""ExperimentFlow (P4 §2-§4, §7-§14): the lifecycle state machine,
approval boundary, review-eligibility, review, and user-decision
mechanisms - built against real persisted DailyIntent/EveningReflection
evidence, never synthetic in-memory shortcuts, matching §20's own
"use real database-backed records... do not fabricate the evidence"
instruction (here via the InMemory reference repositories, which satisfy
the same interface as the SQL-backed ones)."""

from datetime import date

import pytest

from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.evening import EveningReflection, InMemoryEveningReflectionRepository
from app.services.personal_os.experiment import Experiment, ExperimentBaseline
from app.services.personal_os.experiment_flow import ExperimentFlow
from app.services.personal_os.experiment_repository import InMemoryExperimentRepository
from app.services.personal_os.reconciliation import ReconciliationEvidence, reconcile_all
from app.services.personal_os.repository import InMemoryDailyIntentRepository
from app.services.personal_os.shared.types import DayType, ExperimentStatus, ExperimentUserDecision

ORG_ID, USER_ID = 1, 3
CATEGORY = "learning"
DESCRIPTION = "Study transformers"


def _seed(intent_repo, evening_repo, day, status):
    activity = PlannedActivity(description=DESCRIPTION, focus_area=CATEGORY)
    intent = DailyIntent(intent_date=day, stated_intention="x", day_type=DayType.STUDY, planned_activities=(activity,))
    intent_repo.save(intent, organization_id=ORG_ID, user_id=USER_ID)
    evidence = (
        ReconciliationEvidence(explicitly_postponed=True, note="x")
        if status == "postponed"
        else ReconciliationEvidence(explicitly_completed=True)
    )
    evidence_by_description = {DESCRIPTION: evidence}
    reflection = EveningReflection(reflection_date=day, accomplishments=(), evidence_by_activity_description=evidence_by_description)
    reconciliations = reconcile_all((activity,), evidence_by_description)
    evening_repo.save(reflection, reconciliations, organization_id=ORG_ID, user_id=USER_ID, daily_intent_id=intent.intent_id)


def _flow_and_repos():
    intent_repo = InMemoryDailyIntentRepository()
    evening_repo = InMemoryEveningReflectionRepository()
    experiment_repo = InMemoryExperimentRepository()
    flow = ExperimentFlow(intent_repo, evening_repo, experiment_repo)
    return flow, intent_repo, evening_repo, experiment_repo


def _proposed_experiment(experiment_repo, *, baseline_value=4.0, baseline_observations=4):
    baseline = ExperimentBaseline(
        metric="postponement_count",
        category=CATEGORY,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 14),
        value=baseline_value,
        observation_count=baseline_observations,
    )
    experiment = Experiment(
        experiment_id="",
        pattern_id="pattern-1",
        hypothesis_statement="A buffer will reduce postponement.",
        adjustment="Add a 50% buffer to learning-category estimates.",
        measurement_plan="Compare postponement counts against baseline over 14 days.",
        baseline=baseline,
        started_on=date(2026, 7, 16),
        review_date=date(2026, 7, 30),
    )
    return experiment_repo.save(experiment, organization_id=ORG_ID, user_id=USER_ID)


# --- lifecycle transitions (§3) -------------------------------------------------------------------


def test_a_new_experiment_starts_proposed():
    _, _, _, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    assert experiment.status == ExperimentStatus.PROPOSED
    assert experiment.experiment_id != ""


def test_proposed_can_be_approved():
    flow, _, _, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    assert approved.status == ExperimentStatus.APPROVED


def test_approved_can_be_activated():
    flow, _, _, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))
    assert active.status == ExperimentStatus.ACTIVE
    assert active.started_on == date(2026, 7, 16)


def test_active_becomes_ready_for_review_once_the_review_date_arrives():
    flow, intent_repo, evening_repo, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))

    not_yet = flow.list_ready_for_review(organization_id=ORG_ID, user_id=USER_ID, today=date(2026, 7, 20))
    assert not_yet == ()

    ready = flow.list_ready_for_review(organization_id=ORG_ID, user_id=USER_ID, today=date(2026, 7, 30))
    assert len(ready) == 1
    assert ready[0].status == ExperimentStatus.READY_FOR_REVIEW
    assert ready[0].experiment_id == active.experiment_id


def test_ready_for_review_can_be_reviewed():
    flow, intent_repo, evening_repo, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))
    _seed(intent_repo, evening_repo, date(2026, 7, 20), "postponed")
    ready = flow.list_ready_for_review(organization_id=ORG_ID, user_id=USER_ID, today=date(2026, 7, 30))[0]

    reviewed = flow.review(organization_id=ORG_ID, user_id=USER_ID, experiment=ready, today=date(2026, 7, 30))
    assert reviewed.status == ExperimentStatus.REVIEWED
    assert reviewed.comparison is not None


def test_reviewed_can_be_kept_modified_stopped_or_continued():
    flow, intent_repo, evening_repo, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))
    _seed(intent_repo, evening_repo, date(2026, 7, 20), "postponed")
    reviewed = flow.review(organization_id=ORG_ID, user_id=USER_ID, experiment=active, today=date(2026, 7, 30))

    kept = flow.decide(organization_id=ORG_ID, user_id=USER_ID, experiment=reviewed, decision=ExperimentUserDecision.KEEP, today=date(2026, 7, 30))
    assert kept.status == ExperimentStatus.KEPT


# --- invalid transitions are prevented (§3) --------------------------------------------------------


def test_cannot_activate_a_proposed_experiment_without_approval():
    flow, _, _, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    with pytest.raises(ValueError):
        flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment, today=date(2026, 7, 16))


def test_cannot_review_an_experiment_that_was_never_activated():
    flow, _, _, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    with pytest.raises(ValueError):
        flow.review(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment, today=date(2026, 7, 30))


def test_cannot_decide_on_an_experiment_that_has_not_been_reviewed():
    flow, _, _, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))
    with pytest.raises(ValueError):
        flow.decide(organization_id=ORG_ID, user_id=USER_ID, experiment=active, decision=ExperimentUserDecision.KEEP, today=date(2026, 7, 30))


def test_expire_cannot_be_called_on_a_terminal_experiment():
    flow, intent_repo, evening_repo, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))
    _seed(intent_repo, evening_repo, date(2026, 7, 20), "postponed")
    reviewed = flow.review(organization_id=ORG_ID, user_id=USER_ID, experiment=active, today=date(2026, 7, 30))
    stopped = flow.decide(organization_id=ORG_ID, user_id=USER_ID, experiment=reviewed, decision=ExperimentUserDecision.STOP, today=date(2026, 7, 30))
    with pytest.raises(ValueError):
        flow.expire(organization_id=ORG_ID, user_id=USER_ID, experiment=stopped)


def test_expire_can_be_called_on_an_active_experiment_no_one_returned_to():
    flow, _, _, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))
    expired = flow.expire(organization_id=ORG_ID, user_id=USER_ID, experiment=active)
    assert expired.status == ExperimentStatus.EXPIRED


# --- approval boundary (§4) -------------------------------------------------------------------------


def test_experiment_never_becomes_active_merely_because_it_was_proposed():
    _, _, _, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    assert experiment.status != ExperimentStatus.ACTIVE


def test_rejected_experiment_is_never_activated():
    flow, _, _, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    rejected = flow.reject(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment, reason="not now")
    assert rejected.status == ExperimentStatus.STOPPED
    with pytest.raises(ValueError):
        flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=rejected, today=date(2026, 7, 16))


def test_deferred_experiment_remains_available_but_not_active():
    flow, _, _, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    deferred = flow.defer(experiment)
    assert deferred is experiment
    assert deferred.status == ExperimentStatus.PROPOSED


# --- baseline preservation (§5) ----------------------------------------------------------------------


def test_baseline_is_preserved_unchanged_through_approve_and_activate():
    flow, _, _, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo, baseline_value=4.0, baseline_observations=4)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))
    assert active.baseline.value == 4.0
    assert active.baseline.observation_count == 4
    assert active.baseline.period_start == date(2026, 7, 1)
    assert active.baseline.period_end == date(2026, 7, 14)


# --- measurement / evidence selection (§8) --------------------------------------------------------


def test_review_only_counts_evidence_inside_the_measurement_period():
    flow, intent_repo, evening_repo, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))

    _seed(intent_repo, evening_repo, date(2026, 7, 20), "postponed")  # inside [16, 30]
    _seed(intent_repo, evening_repo, date(2026, 8, 5), "postponed")  # outside the measurement period

    reviewed = flow.review(organization_id=ORG_ID, user_id=USER_ID, experiment=active, today=date(2026, 7, 30))
    assert reviewed.comparison.measurement.observation_count == 1


# --- user decisions (§13-§14) -------------------------------------------------------------------------


def test_continue_extends_the_review_date_without_a_new_experiment_id():
    flow, intent_repo, evening_repo, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))
    _seed(intent_repo, evening_repo, date(2026, 7, 20), "postponed")
    reviewed = flow.review(organization_id=ORG_ID, user_id=USER_ID, experiment=active, today=date(2026, 7, 30))

    continued = flow.decide(
        organization_id=ORG_ID, user_id=USER_ID, experiment=reviewed, decision=ExperimentUserDecision.CONTINUE,
        today=date(2026, 7, 30), extended_review_date=date(2026, 8, 13),
    )
    assert continued.status == ExperimentStatus.ACTIVE
    assert continued.review_date == date(2026, 8, 13)
    assert continued.experiment_id == experiment.experiment_id


def test_continue_without_an_explicit_extended_review_date_raises():
    """§14: 'Never silently alter the experiment.'"""
    flow, intent_repo, evening_repo, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))
    _seed(intent_repo, evening_repo, date(2026, 7, 20), "postponed")
    reviewed = flow.review(organization_id=ORG_ID, user_id=USER_ID, experiment=active, today=date(2026, 7, 30))

    with pytest.raises(ValueError):
        flow.decide(organization_id=ORG_ID, user_id=USER_ID, experiment=reviewed, decision=ExperimentUserDecision.CONTINUE, today=date(2026, 7, 30))


def test_modify_requires_modification_notes():
    flow, intent_repo, evening_repo, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))
    _seed(intent_repo, evening_repo, date(2026, 7, 20), "postponed")
    reviewed = flow.review(organization_id=ORG_ID, user_id=USER_ID, experiment=active, today=date(2026, 7, 30))

    with pytest.raises(ValueError):
        flow.decide(organization_id=ORG_ID, user_id=USER_ID, experiment=reviewed, decision=ExperimentUserDecision.MODIFY, today=date(2026, 7, 30))


def test_modify_captures_the_change_and_starts_the_next_measurement_cycle():
    flow, intent_repo, evening_repo, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))
    _seed(intent_repo, evening_repo, date(2026, 7, 20), "postponed")
    reviewed = flow.review(organization_id=ORG_ID, user_id=USER_ID, experiment=active, today=date(2026, 7, 30))

    modified = flow.decide(
        organization_id=ORG_ID, user_id=USER_ID, experiment=reviewed, decision=ExperimentUserDecision.MODIFY,
        today=date(2026, 7, 30), modification_notes="Use a 75% buffer instead of 50%.",
    )
    assert modified.status == ExperimentStatus.APPROVED
    assert modified.adjustment == "Use a 75% buffer instead of 50%."
    assert modified.baseline.value == reviewed.comparison.measurement.value
    assert modified.comparison is None
    assert modified.experiment_id == experiment.experiment_id


def test_stop_preserves_a_provided_reason():
    flow, intent_repo, evening_repo, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))
    _seed(intent_repo, evening_repo, date(2026, 7, 20), "postponed")
    reviewed = flow.review(organization_id=ORG_ID, user_id=USER_ID, experiment=active, today=date(2026, 7, 30))

    stopped = flow.decide(
        organization_id=ORG_ID, user_id=USER_ID, experiment=reviewed, decision=ExperimentUserDecision.STOP,
        today=date(2026, 7, 30), reason="The buffer made planning feel too rigid.",
    )
    assert stopped.status == ExperimentStatus.STOPPED
    assert stopped.decision_reason == "The buffer made planning feel too rigid."


def test_defer_after_review_leaves_the_experiment_unchanged():
    flow, intent_repo, evening_repo, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))
    _seed(intent_repo, evening_repo, date(2026, 7, 20), "postponed")
    reviewed = flow.review(organization_id=ORG_ID, user_id=USER_ID, experiment=active, today=date(2026, 7, 30))

    deferred = flow.decide(organization_id=ORG_ID, user_id=USER_ID, experiment=reviewed, decision=ExperimentUserDecision.DEFER, today=date(2026, 7, 30))
    assert deferred is reviewed
    assert deferred.status == ExperimentStatus.REVIEWED


# --- history (§16) --------------------------------------------------------------------------------


def test_full_lifecycle_history_is_retrievable_and_never_overwritten():
    flow, intent_repo, evening_repo, repo = _flow_and_repos()
    experiment = _proposed_experiment(repo)
    approved = flow.approve(organization_id=ORG_ID, user_id=USER_ID, experiment=experiment)
    active = flow.activate(organization_id=ORG_ID, user_id=USER_ID, experiment=approved, today=date(2026, 7, 16))
    _seed(intent_repo, evening_repo, date(2026, 7, 20), "postponed")
    reviewed = flow.review(organization_id=ORG_ID, user_id=USER_ID, experiment=active, today=date(2026, 7, 30))
    kept = flow.decide(organization_id=ORG_ID, user_id=USER_ID, experiment=reviewed, decision=ExperimentUserDecision.KEEP, today=date(2026, 7, 30))

    history = repo.get_history(organization_id=ORG_ID, user_id=USER_ID, experiment_id=kept.experiment_id)
    assert [h.status for h in history] == [
        ExperimentStatus.PROPOSED,
        ExperimentStatus.APPROVED,
        ExperimentStatus.ACTIVE,
        ExperimentStatus.REVIEWED,
        ExperimentStatus.KEPT,
    ]
    # the original recommendation/baseline/measurement/comparison are all
    # still present in their own version, never rewritten
    assert history[0].baseline.value == 4.0
    assert history[-2].comparison is not None
    assert history[-1].decision == ExperimentUserDecision.KEEP
