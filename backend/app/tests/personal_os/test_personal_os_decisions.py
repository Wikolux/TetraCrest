"""P7.18: pure-function tests for the allowed-action/rollback-candidate
derivation in app/services/personal_os/decisions.py - no repository, no
API, no Runtime involved, matching every other deterministic-core test
on this platform."""

from datetime import date

from app.services.personal_os.adaptation import Adaptation, AdaptationTarget
from app.services.personal_os.decisions import (
    adaptation_allowed_actions,
    experiment_allowed_actions,
    is_adaptation_rollback_candidate,
    pattern_allowed_actions,
)
from app.services.personal_os.experiment import Experiment, ExperimentBaseline, ExperimentComparison, ExperimentMeasurement
from app.services.personal_os.pattern import Pattern
from app.services.personal_os.shared.types import (
    AdaptationScope,
    AdaptationStatus,
    Confidence,
    ExperimentOutcome,
    ExperimentStatus,
    PatternStatus,
    PatternType,
)


def _pattern(status: PatternStatus) -> Pattern:
    return Pattern(
        pattern_id="p1",
        pattern_type=PatternType.REPEATED_POSTPONEMENT,
        observation_window_start=date(2026, 1, 1),
        observation_window_end=date(2026, 1, 7),
        evidence=(),
        observed_facts=(),
        pattern_statement="x",
        confidence=Confidence.MEDIUM,
        status=status,
    )


def _baseline() -> ExperimentBaseline:
    return ExperimentBaseline(metric="hours", category="work", period_start=date(2026, 1, 1), period_end=date(2026, 1, 7), value=10.0, observation_count=5)


def _measurement() -> ExperimentMeasurement:
    return ExperimentMeasurement(metric="hours", category="work", period_start=date(2026, 1, 8), period_end=date(2026, 1, 14), value=6.0, observation_count=5)


def _comparison(outcome: ExperimentOutcome) -> ExperimentComparison:
    return ExperimentComparison(
        baseline=_baseline(), measurement=_measurement(), absolute_change=-4.0, relative_change=-0.4, outcome=outcome, confidence=Confidence.MEDIUM, observation_statement="x"
    )


def _experiment(status: ExperimentStatus, comparison: ExperimentComparison | None = None) -> Experiment:
    return Experiment(
        experiment_id="e1", pattern_id="p1", hypothesis_statement="x", adjustment="x", measurement_plan="x", baseline=_baseline(),
        started_on=date(2026, 1, 1), status=status, comparison=comparison,
    )


def _adaptation(status: AdaptationStatus, outcome_experiment_id: str | None = None) -> Adaptation:
    return Adaptation(
        adaptation_id="a1", target=AdaptationTarget(scope=AdaptationScope.USER, target_id="1"), pattern_id="p1",
        confidence=Confidence.MEDIUM, status=status, outcome_experiment_id=outcome_experiment_id,
    )


# --- pattern_allowed_actions ----------------------------------------------------------------------


def test_pending_confirmation_pattern_has_all_four_responses_allowed():
    actions = pattern_allowed_actions(_pattern(PatternStatus.PENDING_CONFIRMATION))
    assert set(actions) == {"confirm", "reject", "correct", "defer"}


def test_observed_pattern_has_no_allowed_actions():
    assert pattern_allowed_actions(_pattern(PatternStatus.OBSERVED)) == ()


def test_confirmed_pattern_has_no_allowed_actions():
    assert pattern_allowed_actions(_pattern(PatternStatus.CONFIRMED)) == ()


def test_dismissed_pattern_has_no_allowed_actions():
    assert pattern_allowed_actions(_pattern(PatternStatus.DISMISSED)) == ()


# --- experiment_allowed_actions -------------------------------------------------------------------


def test_proposed_experiment_allows_approve_and_reject_only():
    actions = experiment_allowed_actions(_experiment(ExperimentStatus.PROPOSED))
    assert set(actions) == {"approve", "reject"}


def test_reviewed_experiment_allows_all_five_user_decisions():
    actions = experiment_allowed_actions(_experiment(ExperimentStatus.REVIEWED))
    assert set(actions) == {"keep", "modify", "stop", "continue", "defer"}


def test_active_experiment_has_no_allowed_actions():
    assert experiment_allowed_actions(_experiment(ExperimentStatus.ACTIVE)) == ()


def test_approved_experiment_has_no_allowed_actions():
    """APPROVED sits between approval and activation - activate() is an
    operator/orchestration call, never a human decision this surface
    exposes (§8 of the P7.18 brief)."""
    assert experiment_allowed_actions(_experiment(ExperimentStatus.APPROVED)) == ()


def test_kept_experiment_has_no_allowed_actions():
    assert experiment_allowed_actions(_experiment(ExperimentStatus.KEPT)) == ()


# --- adaptation_allowed_actions --------------------------------------------------------------------


def test_proposed_adaptation_allows_approve_and_reject():
    assert set(adaptation_allowed_actions(_adaptation(AdaptationStatus.PROPOSED))) == {"approve", "reject"}


def test_under_evaluation_adaptation_allows_approve_and_reject():
    assert set(adaptation_allowed_actions(_adaptation(AdaptationStatus.UNDER_EVALUATION))) == {"approve", "reject"}


def test_approved_adaptation_allows_only_adopt():
    assert adaptation_allowed_actions(_adaptation(AdaptationStatus.APPROVED)) == ("adopt",)


def test_adopted_adaptation_always_allows_rollback_regardless_of_outcome_signal():
    """ROLLBACK is always technically available on any ADOPTED adaptation
    (AdaptationFlow.rollback()'s own only requirement) - independent of
    whether it is currently flagged as a rollback CANDIDATE for the
    decisions list (§18's own explicit distinction)."""
    assert adaptation_allowed_actions(_adaptation(AdaptationStatus.ADOPTED)) == ("rollback",)


def test_rejected_adaptation_has_no_allowed_actions():
    assert adaptation_allowed_actions(_adaptation(AdaptationStatus.REJECTED)) == ()


def test_rolled_back_adaptation_has_no_allowed_actions():
    assert adaptation_allowed_actions(_adaptation(AdaptationStatus.ROLLED_BACK)) == ()


# --- is_adaptation_rollback_candidate ---------------------------------------------------------------


def test_not_adopted_is_never_a_rollback_candidate():
    outcome = _experiment(ExperimentStatus.REVIEWED, _comparison(ExperimentOutcome.WORSENED))
    assert is_adaptation_rollback_candidate(_adaptation(AdaptationStatus.APPROVED), outcome) is False


def test_adopted_with_no_outcome_experiment_is_not_a_rollback_candidate():
    assert is_adaptation_rollback_candidate(_adaptation(AdaptationStatus.ADOPTED), None) is False


def test_adopted_with_unreviewed_outcome_experiment_is_not_a_rollback_candidate():
    outcome = _experiment(ExperimentStatus.ACTIVE)
    adaptation = _adaptation(AdaptationStatus.ADOPTED, outcome_experiment_id="e1")
    assert is_adaptation_rollback_candidate(adaptation, outcome) is False


def test_adopted_with_improved_outcome_is_not_a_rollback_candidate():
    outcome = _experiment(ExperimentStatus.REVIEWED, _comparison(ExperimentOutcome.IMPROVED))
    adaptation = _adaptation(AdaptationStatus.ADOPTED, outcome_experiment_id="e1")
    assert is_adaptation_rollback_candidate(adaptation, outcome) is False


def test_adopted_with_unchanged_outcome_is_not_a_rollback_candidate():
    outcome = _experiment(ExperimentStatus.REVIEWED, _comparison(ExperimentOutcome.UNCHANGED))
    adaptation = _adaptation(AdaptationStatus.ADOPTED, outcome_experiment_id="e1")
    assert is_adaptation_rollback_candidate(adaptation, outcome) is False


def test_adopted_with_worsened_reviewed_outcome_is_a_rollback_candidate():
    outcome = _experiment(ExperimentStatus.REVIEWED, _comparison(ExperimentOutcome.WORSENED))
    adaptation = _adaptation(AdaptationStatus.ADOPTED, outcome_experiment_id="e1")
    assert is_adaptation_rollback_candidate(adaptation, outcome) is True
