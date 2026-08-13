"""Deterministic experiment measurement (P4 §6, §9-§11): computing a
metric from real evidence, comparing a measurement against its baseline,
and classifying the result - entirely rule-based, never Runtime/LLM
judgement (§11's own explicit instruction: "the underlying result must
come from deterministic calculations"). This module imports neither
RuntimeAdapter nor PromptBuilder, and a dedicated architecture test
(test_personal_os_architecture.py) enforces that it never does, mirroring
pattern_detectors.py's own determinism guarantee exactly.

classify_outcome()'s rule is the one place §9's and §10's two worked
examples are both honored at once: the SAME magnitude of relative change
(a large, "notable" decrease) reads as IMPROVED when there is enough
combined evidence to be reasonably confident (§9: 4 baseline + 1
measurement = 5 observations -> MEDIUM confidence -> IMPROVED), but reads
as INCONCLUSIVE when the sample is too small to say so with more than LOW
confidence (§10: 2 baseline + 1 measurement = 3 observations -> LOW
confidence -> INCONCLUSIVE, never asserted as a genuine improvement).
Confidence is computed by reusing pattern_detectors.calculate_confidence()
directly against the SAME PatternDetectionConfig thresholds Pattern
detection already uses - no second, parallel confidence scale invented.
"""

from app.services.personal_os.experiment import ExperimentBaseline, ExperimentComparison, ExperimentMeasurement
from app.services.personal_os.pattern import PatternEvidenceItem
from app.services.personal_os.pattern_detectors import PatternDetectionConfig, calculate_confidence
from app.services.personal_os.shared.types import Confidence, ExperimentOutcome

# Whether a HIGHER metric value is the better outcome for that metric - a
# small, named, documented dispatch table (P4 §6: "P4 should implement
# only what is necessary," not a generic metric-plugin framework).
# Adding a metric is one new entry here, one new branch in
# calculate_metric(), and one new label in _METRIC_LABELS - never a new
# abstraction layer.
_HIGHER_IS_BETTER: dict[str, bool] = {
    "postponement_count": False,
    "completion_rate": True,
}

_METRIC_LABELS: dict[str, str] = {
    "postponement_count": "postponements",
    "completion_rate": "completion rate",
}

SUPPORTED_METRICS = tuple(_HIGHER_IS_BETTER)


def calculate_metric(evidence: tuple[PatternEvidenceItem, ...], metric: str, category: str) -> tuple[float, int]:
    """Returns (value, observation_count) for one metric, computed only
    from evidence items in the given category - the caller is
    responsible for having already gathered `evidence` over the correct
    window (HistoricalEvidenceReader.gather() with the right
    EvidenceWindow), so this function never itself decides what counts
    as "in range" (§8's "do not count events outside the defined
    measurement period" is enforced by the caller's own window, not
    re-derived here).

    observation_count is the number of category-matching activities
    found - the real sample size a confidence judgement should be based
    on, not merely the numerator of a rate."""
    if metric not in _HIGHER_IS_BETTER:
        raise ValueError(f"Unsupported metric {metric!r} - supported: {SUPPORTED_METRICS}")
    matching = [item for item in evidence if item.activity_category == category]
    if metric == "postponement_count":
        value = float(sum(1 for item in matching if item.status == "postponed"))
    else:  # completion_rate
        value = (sum(1 for item in matching if item.status == "completed") / len(matching)) if matching else 0.0
    return value, len(matching)


def build_baseline(
    evidence: tuple[PatternEvidenceItem, ...], metric: str, category: str, period_start, period_end
) -> ExperimentBaseline | None:
    """§5: only record a baseline when evidence actually exists for this
    category in this window - never fabricate a zero baseline from an
    empty window. A genuine "0 postponements observed across 5 planned
    activities" baseline is legitimate evidence; "0 postponements because
    nothing in this category was even planned" is not evidence of
    anything and must not be recorded - returns None instead, and the
    caller (experiment proposal) must treat that as "cannot propose this
    experiment yet," never silently substitute 0."""
    value, observation_count = calculate_metric(evidence, metric, category)
    if observation_count == 0:
        return None
    return ExperimentBaseline(
        metric=metric, category=category, period_start=period_start, period_end=period_end, value=value, observation_count=observation_count
    )


def build_measurement(
    evidence: tuple[PatternEvidenceItem, ...], metric: str, category: str, period_start, period_end
) -> ExperimentMeasurement:
    """Unlike build_baseline(), always returns a measurement - even
    observation_count=0 is itself a real, reportable fact at review time
    (§8), handled by classify_outcome() as INSUFFICIENT_DATA rather than
    by refusing to construct the measurement at all (a review that finds
    nothing happened during the measurement period is still a review)."""
    value, observation_count = calculate_metric(evidence, metric, category)
    return ExperimentMeasurement(
        metric=metric, category=category, period_start=period_start, period_end=period_end, value=value, observation_count=observation_count
    )


def classify_outcome(
    baseline: ExperimentBaseline, measurement: ExperimentMeasurement, config: PatternDetectionConfig
) -> tuple[ExperimentOutcome, Confidence]:
    """§11's deterministic classification - see this module's own
    docstring for the exact rule and its correspondence to the build
    spec's own two worked examples."""
    if measurement.observation_count == 0:
        return ExperimentOutcome.INSUFFICIENT_DATA, Confidence.LOW

    confidence = calculate_confidence(baseline.observation_count + measurement.observation_count, config)
    higher_is_better = _HIGHER_IS_BETTER[baseline.metric]

    if baseline.value == 0:
        if measurement.value == 0:
            outcome = ExperimentOutcome.UNCHANGED
        else:
            moved_better = measurement.value > baseline.value if higher_is_better else measurement.value < baseline.value
            outcome = ExperimentOutcome.IMPROVED if moved_better else ExperimentOutcome.WORSENED
    else:
        relative_change = (measurement.value - baseline.value) / baseline.value
        if abs(relative_change) < config.change_notable_threshold:
            outcome = ExperimentOutcome.UNCHANGED
        else:
            moved_better = relative_change > 0 if higher_is_better else relative_change < 0
            outcome = ExperimentOutcome.IMPROVED if moved_better else ExperimentOutcome.WORSENED

    # §10's own small-sample caution: a magnitude that would otherwise
    # read as a genuine improvement or decline is downgraded to
    # INCONCLUSIVE - never silently upgraded to a confident claim - when
    # there isn't enough combined evidence to say so.
    if outcome in (ExperimentOutcome.IMPROVED, ExperimentOutcome.WORSENED) and confidence == Confidence.LOW:
        return ExperimentOutcome.INCONCLUSIVE, confidence
    return outcome, confidence


def _observation_statement(baseline: ExperimentBaseline, measurement: ExperimentMeasurement, absolute_change: float, relative_change: float | None, outcome: ExperimentOutcome) -> str:
    """Factual, never causal (§9) - "X decreased by Y%", never "X caused
    a Y% improvement"."""
    label = _METRIC_LABELS.get(baseline.metric, baseline.metric)
    if outcome == ExperimentOutcome.INSUFFICIENT_DATA:
        return (
            f'No evidence was recorded for "{baseline.category}" between {measurement.period_start} and '
            f"{measurement.period_end}, so this cannot be measured yet."
        )
    if relative_change is None:
        return f"{label.capitalize()} moved from {baseline.value:g} to {measurement.value:g} during the experiment period."
    if absolute_change == 0:
        return f"{label.capitalize()} did not change during the experiment period ({baseline.value:g})."
    direction = "increased" if absolute_change > 0 else "decreased"
    return (
        f"{label.capitalize()} {direction} by {abs(relative_change) * 100:.0f}% during the experiment period "
        f"({baseline.value:g} to {measurement.value:g})."
    )


def compare(baseline: ExperimentBaseline, measurement: ExperimentMeasurement, config: PatternDetectionConfig) -> ExperimentComparison:
    """Ties calculate_metric()'s two outputs together into the full,
    deterministic comparison result (§9-§11) - the only function most
    callers need; classify_outcome()/_observation_statement() exist as
    separately testable pieces of this same calculation."""
    if baseline.metric != measurement.metric or baseline.category != measurement.category:
        raise ValueError("compare() requires baseline and measurement to share the same metric and category")

    outcome, confidence = classify_outcome(baseline, measurement, config)
    absolute_change = measurement.value - baseline.value
    relative_change = (
        (measurement.value - baseline.value) / baseline.value
        if measurement.observation_count > 0 and baseline.value != 0
        else None
    )
    statement = _observation_statement(baseline, measurement, absolute_change, relative_change, outcome)

    return ExperimentComparison(
        baseline=baseline,
        measurement=measurement,
        absolute_change=absolute_change,
        relative_change=relative_change,
        outcome=outcome,
        confidence=confidence,
        observation_statement=statement,
    )
