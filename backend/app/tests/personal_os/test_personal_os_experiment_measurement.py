"""Deterministic experiment measurement (P4 §6, §9-§11): metric
calculation, baseline/measurement construction, comparison, and outcome
classification - including both of the build spec's own worked examples
verbatim (§9: 4->1 postponements -> IMPROVED at MEDIUM confidence; §10:
2->1 postponements -> INCONCLUSIVE at LOW confidence, never overclaimed)."""

from datetime import date

import pytest

from app.services.personal_os.experiment_measurement import build_baseline, build_measurement, calculate_metric, classify_outcome, compare
from app.services.personal_os.pattern import PatternEvidenceItem
from app.services.personal_os.pattern_detectors import PatternDetectionConfig
from app.services.personal_os.shared.types import Confidence, ExperimentOutcome

_CONFIG = PatternDetectionConfig()


def _item(day, category="learning", status="postponed"):
    return PatternEvidenceItem(observation_date=date(2026, 7, day), activity_description="Study transformers", activity_category=category, status=status)


# --- calculate_metric -------------------------------------------------------------------------


def test_calculate_metric_counts_postponements_in_category_only():
    evidence = (_item(1, status="postponed"), _item(3, status="postponed"), _item(5, category="delivery", status="postponed"))
    value, count = calculate_metric(evidence, "postponement_count", "learning")
    assert value == 2.0
    assert count == 2


def test_calculate_metric_completion_rate():
    evidence = (_item(1, status="completed"), _item(3, status="completed"), _item(5, status="postponed"), _item(6, status="postponed"))
    value, count = calculate_metric(evidence, "completion_rate", "learning")
    assert value == 0.5
    assert count == 4


def test_calculate_metric_rejects_unsupported_metric():
    with pytest.raises(ValueError):
        calculate_metric((), "unsupported_metric", "learning")


def test_calculate_metric_zero_observations_returns_zero_value_and_zero_count():
    value, count = calculate_metric((), "postponement_count", "learning")
    assert value == 0.0
    assert count == 0


# --- build_baseline / build_measurement (§5, §8) ------------------------------------------------


def test_build_baseline_returns_none_when_no_evidence_exists_for_the_category():
    """§5: never fabricate a baseline from an empty window."""
    evidence = (_item(1, category="delivery"),)
    baseline = build_baseline(evidence, "postponement_count", "learning", date(2026, 7, 1), date(2026, 7, 14))
    assert baseline is None


def test_build_baseline_records_a_real_zero_when_evidence_exists_but_nothing_was_postponed():
    evidence = (_item(1, status="completed"), _item(3, status="completed"))
    baseline = build_baseline(evidence, "postponement_count", "learning", date(2026, 7, 1), date(2026, 7, 14))
    assert baseline is not None
    assert baseline.value == 0.0
    assert baseline.observation_count == 2


def test_build_measurement_always_returns_a_value_even_with_zero_observations():
    """§8: a review that finds nothing happened is still a review -
    unlike build_baseline(), this never returns None."""
    measurement = build_measurement((), "postponement_count", "learning", date(2026, 7, 16), date(2026, 7, 30))
    assert measurement.observation_count == 0
    assert measurement.value == 0.0


def test_baseline_cannot_be_constructed_with_zero_observation_count_directly():
    from app.services.personal_os.experiment import ExperimentBaseline

    with pytest.raises(ValueError):
        ExperimentBaseline(metric="postponement_count", category="learning", period_start=date(2026, 7, 1), period_end=date(2026, 7, 14), value=0.0, observation_count=0)


# --- classify_outcome / compare - the two worked examples (§9, §10) -----------------------------


def test_worked_example_section_9_four_to_one_is_improved_at_medium_confidence():
    baseline = build_baseline(tuple(_item(d) for d in [1, 3, 5, 8]), "postponement_count", "learning", date(2026, 7, 1), date(2026, 7, 14))
    measurement = build_measurement((_item(20),), "postponement_count", "learning", date(2026, 7, 15), date(2026, 7, 28))
    comparison = compare(baseline, measurement, _CONFIG)

    assert comparison.absolute_change == -3.0
    assert comparison.relative_change == -0.75
    assert comparison.outcome == ExperimentOutcome.IMPROVED
    assert comparison.confidence == Confidence.MEDIUM
    assert comparison.observation_statement == "Postponements decreased by 75% during the experiment period (4 to 1)."
    assert "caused" not in comparison.observation_statement.lower()


def test_worked_example_section_10_two_to_one_is_inconclusive_at_low_confidence():
    baseline = build_baseline(tuple(_item(d) for d in [1, 3]), "postponement_count", "learning", date(2026, 7, 1), date(2026, 7, 14))
    measurement = build_measurement((_item(20),), "postponement_count", "learning", date(2026, 7, 15), date(2026, 7, 28))
    comparison = compare(baseline, measurement, _CONFIG)

    assert comparison.outcome == ExperimentOutcome.INCONCLUSIVE
    assert comparison.confidence == Confidence.LOW


def test_insufficient_data_when_measurement_has_zero_observations():
    baseline = build_baseline(tuple(_item(d) for d in [1, 3, 5, 8]), "postponement_count", "learning", date(2026, 7, 1), date(2026, 7, 14))
    measurement = build_measurement((), "postponement_count", "learning", date(2026, 7, 15), date(2026, 7, 28))
    outcome, confidence = classify_outcome(baseline, measurement, _CONFIG)
    assert outcome == ExperimentOutcome.INSUFFICIENT_DATA
    assert confidence == Confidence.LOW


def test_unchanged_when_relative_change_is_below_the_notable_threshold():
    baseline = build_baseline(tuple(_item(d) for d in [1, 3, 5, 8, 10, 12]), "postponement_count", "learning", date(2026, 7, 1), date(2026, 7, 14))
    # 6 baseline postponements, 5 measurement postponements -> ~-17%, below default 20% threshold
    measurement = build_measurement(tuple(_item(d) for d in [16, 18, 20, 22, 24]), "postponement_count", "learning", date(2026, 7, 15), date(2026, 7, 28))
    outcome, _confidence = classify_outcome(baseline, measurement, _CONFIG)
    assert outcome == ExperimentOutcome.UNCHANGED


def test_worsened_for_a_lower_is_better_metric_that_increased_notably():
    baseline = build_baseline(tuple(_item(d) for d in [1, 3]), "postponement_count", "learning", date(2026, 7, 1), date(2026, 7, 14))
    measurement = build_measurement(tuple(_item(d) for d in [16, 18, 20, 22, 24, 26]), "postponement_count", "learning", date(2026, 7, 15), date(2026, 7, 28))
    outcome, confidence = classify_outcome(baseline, measurement, _CONFIG)
    # 2 -> 6 postponements is a clear worsening; combined observations = 8 -> HIGH confidence, not downgraded
    assert outcome == ExperimentOutcome.WORSENED
    assert confidence == Confidence.HIGH


def test_improved_for_a_higher_is_better_metric_that_increased_notably():
    baseline_evidence = tuple(_item(d, status="completed") for d in [1, 3]) + tuple(_item(d, status="postponed") for d in [5, 8, 10, 12])
    baseline = build_baseline(baseline_evidence, "completion_rate", "learning", date(2026, 7, 1), date(2026, 7, 14))
    measurement_evidence = tuple(_item(d, status="completed") for d in [16, 18, 20, 22, 24, 26])
    measurement = build_measurement(measurement_evidence, "completion_rate", "learning", date(2026, 7, 15), date(2026, 7, 28))
    outcome, _confidence = classify_outcome(baseline, measurement, _CONFIG)
    assert outcome == ExperimentOutcome.IMPROVED


def test_zero_baseline_nonzero_measurement_is_worsened_for_postponement_count():
    baseline = build_baseline(tuple(_item(d, status="completed") for d in [1, 3, 5]), "postponement_count", "learning", date(2026, 7, 1), date(2026, 7, 14))
    measurement = build_measurement(tuple(_item(d) for d in [16, 18]), "postponement_count", "learning", date(2026, 7, 15), date(2026, 7, 28))
    comparison = compare(baseline, measurement, _CONFIG)
    assert comparison.relative_change is None  # division by zero baseline is undefined, not zero
    assert comparison.outcome == ExperimentOutcome.WORSENED
    assert "moved from 0 to 2" in comparison.observation_statement


def test_zero_baseline_and_zero_measurement_is_unchanged():
    baseline = build_baseline(tuple(_item(d, status="completed") for d in [1, 3, 5]), "postponement_count", "learning", date(2026, 7, 1), date(2026, 7, 14))
    measurement = build_measurement(tuple(_item(d, status="completed") for d in [16, 18]), "postponement_count", "learning", date(2026, 7, 15), date(2026, 7, 28))
    outcome, _confidence = classify_outcome(baseline, measurement, _CONFIG)
    assert outcome == ExperimentOutcome.UNCHANGED


def test_observation_statement_is_factual_never_causal():
    baseline = build_baseline(tuple(_item(d) for d in [1, 3, 5, 8]), "postponement_count", "learning", date(2026, 7, 1), date(2026, 7, 14))
    measurement = build_measurement((_item(20),), "postponement_count", "learning", date(2026, 7, 15), date(2026, 7, 28))
    comparison = compare(baseline, measurement, _CONFIG)
    forbidden = ("caused", "proves", "because of the buffer", "due to the change")
    for term in forbidden:
        assert term not in comparison.observation_statement.lower()


def test_compare_requires_matching_metric_and_category():
    baseline = build_baseline(tuple(_item(d) for d in [1, 3, 5]), "postponement_count", "learning", date(2026, 7, 1), date(2026, 7, 14))
    measurement = build_measurement(tuple(_item(d) for d in [16]), "postponement_count", "delivery", date(2026, 7, 15), date(2026, 7, 28))
    with pytest.raises(ValueError):
        compare(baseline, measurement, _CONFIG)


# --- determinism (§18) ----------------------------------------------------------------------------


def test_compare_is_deterministic():
    baseline = build_baseline(tuple(_item(d) for d in [1, 3, 5, 8]), "postponement_count", "learning", date(2026, 7, 1), date(2026, 7, 14))
    measurement = build_measurement((_item(20),), "postponement_count", "learning", date(2026, 7, 15), date(2026, 7, 28))
    c1 = compare(baseline, measurement, _CONFIG)
    c2 = compare(baseline, measurement, _CONFIG)
    assert c1.outcome == c2.outcome
    assert c1.confidence == c2.confidence
    assert c1.absolute_change == c2.absolute_change
    assert c1.relative_change == c2.relative_change
    assert c1.observation_statement == c2.observation_statement
