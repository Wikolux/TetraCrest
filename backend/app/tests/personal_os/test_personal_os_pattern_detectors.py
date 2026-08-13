"""Pattern detectors (P3 §3-§9, §18): evidence requirements, each of the
five pattern types, confidence calculation, and determinism.

Every test builds PatternEvidenceItem tuples directly - detectors are
pure functions of (evidence, config), so there is no need to round-trip
through DailyIntent/EveningReflection/HistoricalEvidenceReader here
(that seam is covered separately in test_personal_os_pattern_evidence.py).
"""

from datetime import date

from app.services.personal_os.pattern import PatternEvidenceItem
from app.services.personal_os.pattern_detectors import (
    PatternDetectionConfig,
    calculate_confidence,
    detect_all,
    detect_completion_patterns,
    detect_estimation_accuracy,
    detect_priority_changes,
    detect_recurring_blockers,
    detect_repeated_postponement,
)
from app.services.personal_os.shared.types import Confidence, PatternType

_CONFIG = PatternDetectionConfig()


def _item(day, description="Study transformers", category="learning", status="postponed", estimated=None, actual=None, reason=""):
    return PatternEvidenceItem(
        observation_date=date(2026, 7, day),
        activity_description=description,
        activity_category=category,
        status=status,
        estimated_hours=estimated,
        actual_hours=actual,
        stated_reason=reason,
    )


# --- evidence requirement (§3): one event is never a pattern ------------------------------------


def test_a_single_postponed_event_does_not_produce_a_pattern():
    evidence = (_item(1),)
    assert detect_repeated_postponement(evidence, _CONFIG, "p1") is None


def test_two_postponed_events_below_min_observations_do_not_produce_a_pattern():
    evidence = (_item(1), _item(3))
    assert detect_repeated_postponement(evidence, _CONFIG, "p1") is None


def test_min_observations_worth_of_relevant_events_produces_a_pattern():
    evidence = (_item(1), _item(3), _item(5))
    pattern = detect_repeated_postponement(evidence, _CONFIG, "p1")
    assert pattern is not None
    assert pattern.observation_count == 3


def test_irrelevant_events_are_excluded_from_the_pattern():
    """Completed activities in the same category must not count toward a
    postponement pattern, and a different category's postponements must
    not count toward this one."""
    evidence = (
        _item(1, status="postponed", category="learning"),
        _item(3, status="postponed", category="learning"),
        _item(5, status="postponed", category="learning"),
        _item(6, status="completed", category="learning"),
        _item(7, status="postponed", category="delivery"),
    )
    pattern = detect_repeated_postponement(evidence, _CONFIG, "p1")
    assert pattern.observation_count == 3
    assert all(item.activity_category == "learning" for item in pattern.evidence)
    assert all(item.status == "postponed" for item in pattern.evidence)


def test_evidence_is_traceable_to_specific_dates_and_descriptions():
    evidence = (_item(1, "Study transformers"), _item(3, "Study transformers"), _item(5, "Study RL"))
    pattern = detect_repeated_postponement(evidence, _CONFIG, "p1")
    refs = {fact.evidence_ref for fact in pattern.observed_facts}
    assert refs == {"2026-07-01:Study transformers", "2026-07-03:Study transformers", "2026-07-05:Study RL"}


def test_observation_window_spans_the_earliest_and_latest_evidence():
    evidence = (_item(1), _item(3), _item(8))
    pattern = detect_repeated_postponement(evidence, _CONFIG, "p1")
    assert pattern.observation_window_start == date(2026, 7, 1)
    assert pattern.observation_window_end == date(2026, 7, 8)


# --- confidence (§3) -----------------------------------------------------------------------------


def test_confidence_is_low_below_medium_threshold():
    assert calculate_confidence(3, _CONFIG) == Confidence.LOW


def test_confidence_is_medium_at_medium_threshold():
    assert calculate_confidence(4, _CONFIG) == Confidence.MEDIUM


def test_confidence_is_high_at_high_threshold():
    assert calculate_confidence(6, _CONFIG) == Confidence.HIGH


def test_confidence_thresholds_are_configurable():
    config = PatternDetectionConfig(medium_confidence_min_observations=10, high_confidence_min_observations=20)
    assert calculate_confidence(6, config) == Confidence.LOW


# --- repeated postponement (§5) -------------------------------------------------------------------


def test_repeated_postponement_hypothesis_only_generated_with_multiple_stated_reasons():
    evidence = (_item(1, reason="ran out of time"), _item(3, reason="ran out of time"), _item(5))
    pattern = detect_repeated_postponement(evidence, _CONFIG, "p1")
    assert len(pattern.possible_hypotheses) == 1


def test_repeated_postponement_has_no_hypothesis_without_supporting_reasons():
    evidence = (_item(1), _item(3), _item(5))
    pattern = detect_repeated_postponement(evidence, _CONFIG, "p1")
    assert pattern.possible_hypotheses == ()


def test_repeated_postponement_pattern_type_is_correct():
    evidence = (_item(1), _item(3), _item(5))
    pattern = detect_repeated_postponement(evidence, _CONFIG, "p1")
    assert pattern.pattern_type == PatternType.REPEATED_POSTPONEMENT


# --- estimation accuracy (§6) ---------------------------------------------------------------------


def test_estimation_accuracy_requires_both_estimated_and_actual_hours():
    evidence = (
        _item(1, status="completed", estimated=2.0, actual=4.0),
        _item(3, status="completed", estimated=2.0, actual=4.0),
        _item(5, status="completed", estimated=2.0),  # missing actual - excluded
    )
    pattern = detect_estimation_accuracy(evidence, _CONFIG, "p1")
    assert pattern is None  # only 2 comparable items, below min_observations=3


def test_estimation_accuracy_missing_duration_data_handled_safely():
    evidence = (
        _item(1, status="completed", estimated=2.0, actual=4.0),
        _item(3, status="completed", estimated=2.0, actual=4.0),
        _item(5, status="completed", estimated=2.0, actual=4.0),
        _item(6, status="completed"),  # no duration data at all
    )
    pattern = detect_estimation_accuracy(evidence, _CONFIG, "p1")
    assert pattern is not None
    assert pattern.observation_count == 3


def test_estimation_accuracy_does_not_conclude_why_without_a_notable_ratio():
    evidence = (
        _item(1, status="completed", estimated=2.0, actual=2.1),
        _item(3, status="completed", estimated=2.0, actual=2.0),
        _item(5, status="completed", estimated=2.0, actual=1.9),
    )
    pattern = detect_estimation_accuracy(evidence, _CONFIG, "p1")
    assert pattern.possible_hypotheses == ()


def test_estimation_accuracy_offers_multiple_non_exclusive_hypotheses_when_ratio_is_notable():
    evidence = (
        _item(1, status="completed", estimated=1.0, actual=3.0),
        _item(3, status="completed", estimated=1.0, actual=3.0),
        _item(5, status="completed", estimated=1.0, actual=3.0),
    )
    pattern = detect_estimation_accuracy(evidence, _CONFIG, "p1")
    assert len(pattern.possible_hypotheses) == 1
    statement = pattern.possible_hypotheses[0].statement
    assert "underestimation" in statement and "interruptions" in statement and "scope changes" in statement


# --- recurring blockers (§7) -----------------------------------------------------------------------


def test_recurring_blocker_requires_a_stated_reason():
    evidence = (_item(1, status="blocked"), _item(3, status="blocked"), _item(5, status="blocked"))
    assert detect_recurring_blockers(evidence, _CONFIG, "p1") is None


def test_recurring_blocker_groups_by_dependency_class_not_activity():
    evidence = (
        _item(1, description="Ship report", status="blocked", reason="waiting on legal to review"),
        _item(3, description="Ship deck", status="blocked", reason="waiting on legal to review"),
        _item(5, description="Ship memo", status="blocked", reason="waiting on legal to review"),
    )
    pattern = detect_recurring_blockers(evidence, _CONFIG, "p1")
    assert pattern is not None
    assert "dependency on another person" in pattern.pattern_statement


def test_a_single_blocked_event_is_not_a_recurring_blocker():
    evidence = (_item(1, status="blocked", reason="waiting on legal"),)
    assert detect_recurring_blockers(evidence, _CONFIG, "p1") is None


def test_recurring_blocker_categories_are_keyword_derived():
    evidence = (
        _item(1, status="blocked", reason="stuck in back-to-back meetings"),
        _item(3, status="blocked", reason="another meeting ran long"),
        _item(5, status="blocked", reason="meeting overran again"),
    )
    pattern = detect_recurring_blockers(evidence, _CONFIG, "p1")
    assert "meetings" in pattern.pattern_statement


# --- priority changes (§8) -------------------------------------------------------------------------


def test_priority_change_below_min_observations_is_not_detected():
    evidence = (_item(1, status="superseded"), _item(3, status="superseded"))
    assert detect_priority_changes(evidence, _CONFIG, "p1") is None


def test_priority_change_distinguishes_external_from_other_triggers():
    evidence = (
        _item(1, status="superseded", reason="a higher-priority request came in"),
        _item(3, status="superseded", reason="a higher-priority request came in"),
        _item(5, status="superseded", reason="priorities changed"),
        _item(6, status="superseded", reason="just felt like doing something else"),
    )
    pattern = detect_priority_changes(evidence, _CONFIG, "p1")
    assert "3 of those changes were triggered by a stated higher-priority external commitment" in pattern.pattern_statement


def test_priority_change_is_not_automatically_treated_as_planning_failure():
    """§8's own worked example: every change externally triggered should
    surface an adaptive-planning hypothesis, never a failure framing."""
    evidence = (
        _item(1, status="superseded", reason="higher-priority request"),
        _item(3, status="superseded", reason="higher-priority request"),
        _item(5, status="superseded", reason="higher-priority request"),
    )
    pattern = detect_priority_changes(evidence, _CONFIG, "p1")
    assert len(pattern.possible_hypotheses) == 1
    statement = pattern.possible_hypotheses[0].statement.lower()
    assert "adaptive" in statement
    # "rather than plan abandonment" is the honest contrast this hypothesis
    # draws - what would be wrong is asserting abandonment as fact, which
    # this phrasing explicitly does not do.
    assert "this appears to be" in statement or "rather than" in statement


# --- completion patterns (§9) ---------------------------------------------------------------------


def test_completion_pattern_requires_min_observations_in_a_category():
    evidence = (_item(1, category="delivery", status="completed"), _item(3, category="delivery", status="completed"))
    assert detect_completion_patterns(evidence, _CONFIG, "p1") is None


def test_completion_pattern_uses_appears_associated_with_language_not_causal_language():
    evidence = tuple(_item(d, category="delivery", status="completed") for d in (1, 2, 3))
    pattern = detect_completion_patterns(evidence, _CONFIG, "p1")
    assert pattern is not None
    assert "appear associated with" in pattern.pattern_statement
    assert "causes" not in pattern.pattern_statement.lower()


def test_completion_pattern_not_detected_below_notable_completion_rate():
    evidence = (
        _item(1, category="delivery", status="completed"),
        _item(2, category="delivery", status="postponed"),
        _item(3, category="delivery", status="postponed"),
    )
    assert detect_completion_patterns(evidence, _CONFIG, "p1") is None


# --- determinism (§18) ----------------------------------------------------------------------------


def test_detect_all_is_deterministic_for_the_same_evidence_and_config():
    evidence = (
        _item(1, status="postponed", reason="ran out of time"),
        _item(3, status="postponed", reason="ran out of time"),
        _item(5, status="postponed"),
        _item(6, category="delivery", status="completed"),
        _item(7, category="delivery", status="completed"),
        _item(8, category="delivery", status="completed"),
    )
    ids = iter(["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"])
    patterns_1 = detect_all(evidence, _CONFIG, lambda: next(ids))

    ids_2 = iter(["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"])
    patterns_2 = detect_all(evidence, _CONFIG, lambda: next(ids_2))

    assert len(patterns_1) == len(patterns_2)
    for p1, p2 in zip(patterns_1, patterns_2):
        assert p1.pattern_type == p2.pattern_type
        assert p1.pattern_statement == p2.pattern_statement
        assert p1.confidence == p2.confidence
        assert p1.observation_count == p2.observation_count


def test_detect_all_never_constructs_a_pattern_from_insufficient_evidence():
    evidence = (_item(1), _item(3))  # below min_observations for every detector
    patterns = detect_all(evidence, _CONFIG, lambda: "x")
    assert patterns == ()
