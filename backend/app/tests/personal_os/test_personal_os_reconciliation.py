"""Task reconciliation (§6): the eight-status distinction, and the rule
that "not completed" is never automatically "failure.\""""

from app.services.personal_os.daily_intent import PlannedActivity
from app.services.personal_os.reconciliation import ReconciliationEvidence, reconcile, reconcile_all
from app.services.personal_os.shared.types import ReconciliationStatus


def _activity(description="Draft the proposal"):
    return PlannedActivity(description=description)


def test_no_evidence_reconciles_to_unknown_never_incomplete():
    record = reconcile(_activity(), evidence=None)
    assert record.status == ReconciliationStatus.UNKNOWN


def test_unfinished_work_is_not_automatically_classified_as_failure():
    """No status here is named or treated as "failure." reconcile()
    itself never assigns INCOMPLETE by default for a not-completed item
    with no other evidence - it assigns UNKNOWN, honestly reflecting that
    "not completed" and "incomplete" are not the same claim without
    further evidence."""
    assert "failure" not in {status.value for status in ReconciliationStatus}
    not_completed_activity = _activity("Something not marked done")
    record = reconcile(not_completed_activity, evidence=None)
    assert record.status != ReconciliationStatus.INCOMPLETE
    assert record.status == ReconciliationStatus.UNKNOWN


def test_explicit_completion_reconciles_to_completed():
    record = reconcile(_activity(), ReconciliationEvidence(explicitly_completed=True))
    assert record.status == ReconciliationStatus.COMPLETED


def test_intentional_postponement_is_distinguishable_from_cancellation():
    postponed = reconcile(_activity(), ReconciliationEvidence(explicitly_postponed=True))
    cancelled = reconcile(_activity(), ReconciliationEvidence(explicitly_cancelled=True))
    assert postponed.status == ReconciliationStatus.POSTPONED
    assert cancelled.status == ReconciliationStatus.CANCELLED
    assert postponed.status != cancelled.status


def test_intentional_postponement_is_distinguishable_from_unknown():
    postponed = reconcile(_activity(), ReconciliationEvidence(explicitly_postponed=True))
    unknown = reconcile(_activity(), evidence=None)
    assert postponed.status != unknown.status


def test_blocked_status_is_distinct_from_postponed():
    record = reconcile(_activity(), ReconciliationEvidence(explicitly_blocked=True))
    assert record.status == ReconciliationStatus.BLOCKED


def test_rested_instead_is_a_valid_non_failure_outcome():
    record = reconcile(_activity(), ReconciliationEvidence(explicitly_rested_instead=True))
    assert record.status == ReconciliationStatus.RESTED


def test_changed_priorities_can_supersede_previous_plans():
    record = reconcile(_activity(), ReconciliationEvidence(superseding_priority="Apply for jobs instead"))
    assert record.status == ReconciliationStatus.SUPERSEDED
    assert record.evidence.superseding_priority == "Apply for jobs instead"


def test_completion_takes_precedence_over_a_stale_superseding_note():
    record = reconcile(_activity(), ReconciliationEvidence(explicitly_completed=True, superseding_priority="ignored"))
    assert record.status == ReconciliationStatus.COMPLETED


def test_reconcile_all_matches_evidence_by_activity_description():
    activities = (_activity("A"), _activity("B"))
    evidence = {"A": ReconciliationEvidence(explicitly_completed=True)}
    records = reconcile_all(activities, evidence)
    assert records[0].status == ReconciliationStatus.COMPLETED
    assert records[1].status == ReconciliationStatus.UNKNOWN  # B has no evidence - honestly UNKNOWN, not assumed
