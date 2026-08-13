"""Task reconciliation (§6 of the build spec): classifying what happened
to yesterday's planned activities, without ever defaulting "not
completed" to "failure."

reconcile() is a pure function - same PlannedActivity + same evidence in,
same ReconciliationRecord out, deterministic and independently testable,
the same discipline every deterministic planner on this platform already
follows (ExecutivePlanner, every SpecialistPlanner, InsightEngine).
"""

from dataclasses import dataclass

from app.services.personal_os.daily_intent import PlannedActivity
from app.services.personal_os.shared.types import ReconciliationStatus


@dataclass(frozen=True)
class ReconciliationEvidence:
    """What Personal OS actually knows about one planned activity, from
    yesterday's evening reflection or explicit user statement today -
    never inferred from silence. A PlannedActivity with no
    ReconciliationEvidence at all reconciles to UNKNOWN, never
    INCOMPLETE.

    actual_hours (P3) is optional and additive, the counterpart to
    PlannedActivity.estimated_hours - only meaningful when the activity
    was actually worked on (typically alongside explicitly_completed),
    never required, since most evidence still comes from free-form text
    with no duration mentioned at all."""

    explicitly_completed: bool = False
    explicitly_postponed: bool = False
    explicitly_cancelled: bool = False
    explicitly_blocked: bool = False
    explicitly_rested_instead: bool = False
    superseding_priority: str = ""
    note: str = ""
    actual_hours: float | None = None


@dataclass(frozen=True)
class ReconciliationRecord:
    """One PlannedActivity's outcome, with the evidence that justified
    the classification - never just the status alone, so a caller can
    always see why, not only what."""

    activity: PlannedActivity
    status: ReconciliationStatus
    evidence: ReconciliationEvidence


def reconcile(activity: PlannedActivity, evidence: ReconciliationEvidence | None) -> ReconciliationRecord:
    """Classify one activity's outcome from explicit evidence only.

    Precedence matters when more than one explicit flag is set (e.g. a
    user both marks something blocked and notes a superseding priority):
    cancellation and completion are the most definite outward states and
    are checked first; supersession only applies once cancellation/
    completion/postponement/blocking are all ruled out, since a
    superseding priority alone does not tell us what became of the
    original activity.
    """
    if evidence is None:
        return ReconciliationRecord(activity, ReconciliationStatus.UNKNOWN, ReconciliationEvidence())

    if evidence.explicitly_completed:
        status = ReconciliationStatus.COMPLETED
    elif evidence.explicitly_cancelled:
        status = ReconciliationStatus.CANCELLED
    elif evidence.explicitly_rested_instead:
        status = ReconciliationStatus.RESTED
    elif evidence.explicitly_blocked:
        status = ReconciliationStatus.BLOCKED
    elif evidence.explicitly_postponed:
        status = ReconciliationStatus.POSTPONED
    elif evidence.superseding_priority:
        status = ReconciliationStatus.SUPERSEDED
    else:
        status = ReconciliationStatus.UNKNOWN

    return ReconciliationRecord(activity, status, evidence)


def reconcile_all(
    activities: tuple[PlannedActivity, ...],
    evidence_by_description: dict[str, ReconciliationEvidence],
) -> tuple[ReconciliationRecord, ...]:
    """Reconcile every planned activity from yesterday against whatever
    evidence exists for it, keyed by the activity's own description -
    an activity with no matching key gets evidence=None (UNKNOWN), never
    silently dropped or assumed incomplete."""
    return tuple(reconcile(activity, evidence_by_description.get(activity.description)) for activity in activities)
