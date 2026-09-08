"""adaptation_outcome.py (P7.12): resolving an Adaptation's own ADOPTED
timestamp from durable history, the day-after-adoption precision
boundary, and the plain, non-binding recommendation mapping - entirely
deterministic, no Runtime/PromptBuilder involved."""

from datetime import UTC, date, datetime

from app.services.personal_os.adaptation import Adaptation, AdaptationTarget
from app.services.personal_os.adaptation_outcome import earliest_measurable_start, recommend_next_step, resolve_adopted_at
from app.services.personal_os.shared.types import AdaptationScope, AdaptationStatus, Confidence, ExperimentOutcome

ORG_ID, USER_ID = 1, 20


def _adaptation(status=AdaptationStatus.PROPOSED, updated_at=None):
    kwargs = {}
    if updated_at is not None:
        kwargs["updated_at"] = updated_at
    return Adaptation(
        adaptation_id="a1",
        target=AdaptationTarget(scope=AdaptationScope.USER_PREFERENCE, target_id=str(USER_ID)),
        pattern_id="p1",
        confidence=Confidence.MEDIUM,
        status=status,
        **kwargs,
    )


# --- resolve_adopted_at ------------------------------------------------------------------------------


def test_resolve_adopted_at_returns_none_when_never_adopted():
    history = (_adaptation(status=AdaptationStatus.PROPOSED), _adaptation(status=AdaptationStatus.UNDER_EVALUATION))
    assert resolve_adopted_at(history) is None


def test_resolve_adopted_at_returns_the_adopted_versions_own_timestamp():
    adopted_at = datetime(2026, 7, 15, 14, 30, tzinfo=UTC)
    history = (
        _adaptation(status=AdaptationStatus.PROPOSED, updated_at=datetime(2026, 7, 1, tzinfo=UTC)),
        _adaptation(status=AdaptationStatus.UNDER_EVALUATION, updated_at=datetime(2026, 7, 5, tzinfo=UTC)),
        _adaptation(status=AdaptationStatus.APPROVED, updated_at=datetime(2026, 7, 10, tzinfo=UTC)),
        _adaptation(status=AdaptationStatus.ADOPTED, updated_at=adopted_at),
    )
    assert resolve_adopted_at(history) == adopted_at


def test_resolve_adopted_at_ignores_later_terminal_versions():
    """Rollback/supersession happen AFTER adoption - the adoption
    instant itself never moves just because the adaptation was later
    rolled back."""
    adopted_at = datetime(2026, 7, 15, tzinfo=UTC)
    history = (
        _adaptation(status=AdaptationStatus.ADOPTED, updated_at=adopted_at),
        _adaptation(status=AdaptationStatus.ROLLED_BACK, updated_at=datetime(2026, 8, 1, tzinfo=UTC)),
    )
    assert resolve_adopted_at(history) == adopted_at


def test_resolve_adopted_at_empty_history():
    assert resolve_adopted_at(()) is None


# --- earliest_measurable_start (the day-after-adoption precision boundary) --------------------------


def test_earliest_measurable_start_is_the_day_after_adoption():
    adopted_at = datetime(2026, 7, 15, 23, 59, tzinfo=UTC)
    assert earliest_measurable_start(adopted_at) == date(2026, 7, 16)


def test_earliest_measurable_start_excludes_the_adoption_day_regardless_of_time_of_day():
    """Adoption at 00:01 and adoption at 23:59 both exclude the SAME
    calendar day - day-level Experiment evidence cannot resolve sub-day
    causality, so the whole adoption day is deliberately out of bounds."""
    early = earliest_measurable_start(datetime(2026, 7, 15, 0, 1, tzinfo=UTC))
    late = earliest_measurable_start(datetime(2026, 7, 15, 23, 59, tzinfo=UTC))
    assert early == late == date(2026, 7, 16)


# --- recommend_next_step: plain, non-binding, causality-safe ----------------------------------------


def test_recommend_next_step_covers_every_experiment_outcome():
    for outcome in ExperimentOutcome:
        recommendation = recommend_next_step(outcome)
        assert isinstance(recommendation, str)
        assert recommendation


def test_recommend_next_step_never_overclaims_causation_for_improved_or_worsened():
    assert "causality has not been established" in recommend_next_step(ExperimentOutcome.IMPROVED)
    assert "causality has not been established" in recommend_next_step(ExperimentOutcome.WORSENED)


def test_recommend_next_step_insufficient_data_never_reaches_a_conclusion():
    recommendation = recommend_next_step(ExperimentOutcome.INSUFFICIENT_DATA)
    assert "not enough evidence" in recommendation.lower()
    assert "no behavioral decision" in recommendation.lower()
