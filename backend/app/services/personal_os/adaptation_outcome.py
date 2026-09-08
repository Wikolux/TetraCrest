"""Deterministic post-adoption outcome resolution (P7.12): finding when
an Adaptation was actually adopted, drawing the honest precision boundary
between "before" and "after" that a whole-day `Experiment` can support,
and turning an already-computed `ExperimentComparison` into a plain,
non-binding recommendation - never a decision Personal OS makes on the
user's behalf.

Mirrors experiment_measurement.py's own "entirely rule-based, never
Runtime/LLM judgement" discipline exactly: this module imports neither
RuntimeAdapter nor PromptBuilder, and a dedicated architecture test
enforces that it never does. It computes nothing an Experiment doesn't
already compute for itself - see adaptation_outcome_flow.py for how this
is wired into the real Experiment lifecycle.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.services.personal_os.adaptation import Adaptation
from app.services.personal_os.experiment import Experiment
from app.services.personal_os.shared.types import AdaptationStatus, ExperimentOutcome


def resolve_adopted_at(history: tuple[Adaptation, ...]) -> datetime | None:
    """The first version in `history` (oldest-first, exactly how
    AdaptationRepository.get_history() already orders it) whose status
    is ADOPTED - its own `updated_at` is the moment adopt() actually ran.

    `updated_at`, not `created_at`, is the correct field for BOTH
    backends, verified from source rather than assumed: `created_at`
    stays fixed at the ORIGINAL proposal's timestamp across every later
    version for the in-memory backend (dataclasses.replace() never
    touches it), so it cannot tell you when THIS version was created;
    `updated_at` is freshly set by AdaptationFlow._save() on every
    transition for the in-memory backend, and is independently set to
    the database's own INSERT-time clock for the SQL backend (every
    lifecycle transition is a new row, never an UPDATE, so `onupdate`
    never fires and `updated_at` gets a fresh `func.now()` per version
    exactly like `created_at` does there) - `updated_at` is the one
    field whose semantics ("when did this specific version happen") are
    actually consistent across both repository implementations.

    Returns None if this Adaptation was never adopted (its history
    contains no ADOPTED version at all)."""
    for version in history:
        if version.status == AdaptationStatus.ADOPTED:
            return version.updated_at
    return None


def earliest_measurable_start(adopted_at: datetime) -> date:
    """P7.12's own precision boundary, made explicit rather than assumed:
    `Experiment` measures in whole `date`s, but `adopted_at` is a
    `datetime` - adoption could have happened at any moment during its
    own calendar day, so that day's evidence may honestly contain a mix
    of pre- and post-adoption behavior that day-level data cannot
    separate. Rather than pretend day-level evidence gives sub-day
    causal precision, the post-adoption measurement window is defined to
    start the day AFTER adoption, never the adoption day itself - the
    adoption day is deliberately excluded from measurement entirely."""
    return adopted_at.date() + timedelta(days=1)


@dataclass(frozen=True)
class AdaptationOutcomeReview:
    """One review's own result - the Experiment's own, already
    deterministic, already causality-safe `ExperimentComparison`
    (reached via `experiment.comparison` after review), plus whether the
    measured Adaptation is STILL the currently adopted one. A rolled-
    back or superseded Adaptation's own measurement stays historically
    valid and is never discarded, but must never be presented as
    evidence about a currently active preference - `is_currently_adopted`
    and `adaptation_status` exist so a caller can honestly frame which
    case this is, and `recommendation` is a plain, non-binding label,
    never a decision this module or any caller makes automatically."""

    experiment: Experiment
    adaptation_status: AdaptationStatus
    is_currently_adopted: bool
    recommendation: str


_INSUFFICIENT_DATA_RECOMMENDATION = "Not enough evidence yet to draw any conclusion - no behavioral decision should be made from this alone."

_RECOMMENDATIONS: dict[ExperimentOutcome, str] = {
    ExperimentOutcome.IMPROVED: "Consider keeping this preference - the evidence is consistent with it helping, though causality has not been established.",
    ExperimentOutcome.UNCHANGED: "Consider continuing to observe, or reviewing whether this preference is the right lever at all.",
    ExperimentOutcome.WORSENED: "Consider modifying or rolling back this preference - the evidence is consistent with it not helping, though causality has not been established.",
    ExperimentOutcome.INCONCLUSIVE: "Consider continuing to observe - there is an early signal but not enough evidence to act on yet.",
    ExperimentOutcome.INSUFFICIENT_DATA: _INSUFFICIENT_DATA_RECOMMENDATION,
}


def recommend_next_step(outcome: ExperimentOutcome) -> str:
    """P7.12 §9: a plain, non-binding recommendation - reuses
    ExperimentOutcome exactly as-is (no duplicate enum, no new
    vocabulary), and never itself calls ExperimentFlow.decide(),
    AdaptationFlow.rollback(), or AdaptationFlow.propose_relearn(). The
    mapping is deliberately conservative: every recommendation for a
    genuine IMPROVED/WORSENED reading still names that "causality has
    not been established," mirroring experiment_flow.py's own existing
    fallback narration exactly rather than inventing a second causality
    discipline."""
    return _RECOMMENDATIONS[outcome]
