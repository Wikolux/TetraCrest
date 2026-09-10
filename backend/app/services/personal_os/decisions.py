"""P7.18: pure, deterministic derivation of "what is currently actionable"
for one Pattern/Experiment/Adaptation - never a workflow engine, never a
second lifecycle definition. Every function here only restates a rule
already enforced elsewhere (pattern_flow.py's implicit PENDING_CONFIRMATION
gate, experiment_flow.py's/adaptation_flow.py's own explicit
`_require_status()` checks) in a form the API layer can read without
duplicating each flow's own internal guard clauses.

is_adaptation_rollback_candidate() is the one function that looks past a
single entity's own status: it reuses adaptation_outcome.py's existing,
already-tested ExperimentOutcome -> recommendation mapping
(`recommend_next_step`) to decide whether an ADOPTED adaptation's own
already-measured, already-reviewed outcome experiment gives a real,
structured reason to surface it - never inventing a new signal, never
itself calling ExperimentFlow.review() (a mutating transition) to produce
one. An ADOPTED adaptation with no linked outcome experiment, or one not
yet reviewed, is never a rollback candidate - "no signal yet" is not
"something is wrong."""

from app.services.personal_os.adaptation import Adaptation
from app.services.personal_os.experiment import Experiment
from app.services.personal_os.pattern import Pattern
from app.services.personal_os.shared.types import (
    AdaptationStatus,
    ExperimentOutcome,
    ExperimentStatus,
    ExperimentUserDecision,
    PatternStatus,
    UserPatternResponse,
)

PATTERN_APPROVAL_ACTIONS: tuple[str, ...] = tuple(response.value for response in UserPatternResponse)
EXPERIMENT_APPROVAL_ACTIONS: tuple[str, ...] = ("approve", "reject")
EXPERIMENT_REVIEW_ACTIONS: tuple[str, ...] = tuple(decision.value for decision in ExperimentUserDecision)
ADAPTATION_APPROVAL_ACTIONS: tuple[str, ...] = ("approve", "reject")
ADAPTATION_ADOPTION_ACTIONS: tuple[str, ...] = ("adopt",)
ADAPTATION_ROLLBACK_ACTIONS: tuple[str, ...] = ("rollback",)

_UNFAVORABLE_OUTCOMES = (ExperimentOutcome.WORSENED,)


def pattern_allowed_actions(pattern: Pattern) -> tuple[str, ...]:
    """PatternDetectionFlow.respond() itself enforces no status guard -
    this is the one place that rule is actually expressed, so the API
    layer can refuse an out-of-lifecycle response (409) before ever
    calling into the flow, rather than relying on respond() to reject it
    (it won't - see the P7.18 closure report's own "no lifecycle guard
    in respond()" finding)."""
    if pattern.status == PatternStatus.PENDING_CONFIRMATION:
        return PATTERN_APPROVAL_ACTIONS
    return ()


def experiment_allowed_actions(experiment: Experiment) -> tuple[str, ...]:
    if experiment.status == ExperimentStatus.PROPOSED:
        return EXPERIMENT_APPROVAL_ACTIONS
    if experiment.status == ExperimentStatus.REVIEWED:
        return EXPERIMENT_REVIEW_ACTIONS
    return ()


def adaptation_allowed_actions(adaptation: Adaptation) -> tuple[str, ...]:
    """ROLLBACK is always returned for any ADOPTED adaptation - it is a
    real, always-available action per AdaptationFlow.rollback()'s own
    guard (status == ADOPTED is its only requirement). Whether an ADOPTED
    adaptation is additionally worth SURFACING in the decisions list is a
    separate question - see is_adaptation_rollback_candidate()."""
    if adaptation.status in (AdaptationStatus.PROPOSED, AdaptationStatus.UNDER_EVALUATION):
        return ADAPTATION_APPROVAL_ACTIONS
    if adaptation.status == AdaptationStatus.APPROVED:
        return ADAPTATION_ADOPTION_ACTIONS
    if adaptation.status == AdaptationStatus.ADOPTED:
        return ADAPTATION_ROLLBACK_ACTIONS
    return ()


def is_adaptation_rollback_candidate(adaptation: Adaptation, outcome_experiment: Experiment | None) -> bool:
    """True only when ALL of: this adaptation is currently ADOPTED, it
    has a linked outcome experiment, that experiment has already been
    reviewed (status == REVIEWED, comparison already computed by some
    prior, separate call to ExperimentFlow.review() - never triggered
    here), and the measured outcome is unfavorable (WORSENED). No new
    business rule: WORSENED is the one ExperimentOutcome
    adaptation_outcome.py's own existing `recommend_next_step()` already
    maps to a rollback/modify recommendation."""
    if adaptation.status != AdaptationStatus.ADOPTED:
        return False
    if outcome_experiment is None:
        return False
    if outcome_experiment.status != ExperimentStatus.REVIEWED:
        return False
    if outcome_experiment.comparison is None:
        return False
    return outcome_experiment.comparison.outcome in _UNFAVORABLE_OUTCOMES
