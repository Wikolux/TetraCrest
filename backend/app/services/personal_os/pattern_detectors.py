"""Pattern detection (P3 §4-§9): the smallest useful initial set of five
detectors, each a pure function of (evidence, config) - same evidence,
same config, same Pattern out, the same determinism discipline every
planner on this platform already follows (§18).

PatternDetectionConfig's thresholds are named, documented, and
configurable (§3's own explicit requirement) rather than invented ad
hoc:

- min_observations=3: the floor below which this module refuses to call
  something a pattern at all. Not arbitrary - it is the spec's own
  worked example count ("three similar activities were postponed"), one
  above InferredPattern's own already-existing structural floor
  (reasoning.py requires >=2 supporting_facts; 3 is deliberately higher,
  since "a pattern," as opposed to "the bare minimum reasoning.py will
  accept," should mean more than the two-observation floor that type
  enforces everywhere on this platform).
- window_days=14: "the last two weeks," the more specific of the two
  window sizes P3's own worked examples use ("the last eight days," "the
  last two weeks") - the wider window is the safer default, since it
  never excludes evidence a narrower one would have included.

Every detector returns None, never a low-quality Pattern, when evidence
is insufficient - "do not construct a meaningful behavioural pattern
from one isolated event" (§3) is enforced by returning nothing, not by
constructing something and hoping a caller checks confidence.
"""

from dataclasses import dataclass

from app.services.personal_os.pattern import Pattern, PatternEvidenceItem
from app.services.personal_os.reasoning import Hypothesis, InferredPattern, ObservedFact
from app.services.personal_os.shared.types import Confidence, PatternType

_EXTERNAL_TRIGGER_MARKERS = ("priorities changed", "higher-priority", "higher priority", "more important", "urgent")
_COMPLETION_RATE_NOTABLE = 0.8


@dataclass(frozen=True)
class PatternDetectionConfig:
    """Every threshold this module uses, named and overridable - never a
    bare literal buried in a detector's own body."""

    window_days: int = 14
    min_observations: int = 3
    high_confidence_min_observations: int = 6
    medium_confidence_min_observations: int = 4
    estimation_ratio_notable_threshold: float = 1.5
    # P4's own experiment_measurement.py reuses this same config object
    # (§10: "reuse existing Confidence where appropriate") rather than
    # inventing a second config class - a relative change below this
    # threshold classifies as UNCHANGED, not IMPROVED/WORSENED. 0.20 is
    # the same order of magnitude as estimation_ratio_notable_threshold
    # above (a 1.5x ratio is a 50% relative change) but deliberately
    # lower, since "notable" for a percentage-point-scale comparison
    # (postponement counts, completion rates) is a smaller bar than
    # "notable" for a multiplicative time-estimate ratio.
    change_notable_threshold: float = 0.20


def calculate_confidence(observation_count: int, config: PatternDetectionConfig) -> Confidence:
    """More observations -> higher confidence - a plain, documented
    step function, never a fabricated numeric probability (matching the
    same discipline InsightEngine and every specialist's own confidence
    handling already follows platform-wide)."""
    if observation_count >= config.high_confidence_min_observations:
        return Confidence.HIGH
    if observation_count >= config.medium_confidence_min_observations:
        return Confidence.MEDIUM
    return Confidence.LOW


def _facts_from_items(items: tuple[PatternEvidenceItem, ...]) -> tuple[ObservedFact, ...]:
    return tuple(
        ObservedFact(
            statement=f'"{item.activity_description}" ({item.activity_category}) on {item.observation_date}: {item.status}'
            + (f" - {item.stated_reason}" if item.stated_reason else ""),
            evidence_ref=f"{item.observation_date}:{item.activity_description}",
        )
        for item in items
    )


def _window(items: tuple[PatternEvidenceItem, ...]):
    dates = [item.observation_date for item in items]
    return min(dates), max(dates)


def detect_repeated_postponement(
    evidence: tuple[PatternEvidenceItem, ...], config: PatternDetectionConfig, pattern_id: str
) -> Pattern | None:
    """§5: comparable activities repeatedly postponed - grouped by
    activity_category, never by exact description (two differently-worded
    but same-category activities should still count toward one pattern)."""
    postponed = [item for item in evidence if item.status == "postponed"]
    by_category: dict[str, list[PatternEvidenceItem]] = {}
    for item in postponed:
        by_category.setdefault(item.activity_category, []).append(item)

    best_category, best_items = max(by_category.items(), key=lambda kv: len(kv[1]), default=(None, []))
    if best_category is None or len(best_items) < config.min_observations:
        return None

    start, end = _window(tuple(best_items))
    statement = (
        f'{len(best_items)} "{best_category}" activities were postponed between {start} and {end}: '
        + ", ".join(f'"{item.activity_description}" ({item.observation_date})' for item in best_items)
    )
    facts = _facts_from_items(tuple(best_items))
    confidence = calculate_confidence(len(best_items), config)
    hypotheses = _postponement_hypotheses(best_items, facts)

    return Pattern(
        pattern_id=pattern_id,
        pattern_type=PatternType.REPEATED_POSTPONEMENT,
        observation_window_start=start,
        observation_window_end=end,
        evidence=tuple(best_items),
        observed_facts=facts,
        pattern_statement=statement,
        confidence=confidence,
        possible_hypotheses=hypotheses,
    )


def _postponement_hypotheses(items: list[PatternEvidenceItem], facts: tuple[ObservedFact, ...]) -> tuple[Hypothesis, ...]:
    reasons = [item.stated_reason for item in items if item.stated_reason]
    if len(reasons) < 2:
        # Not enough stated reasons to hypothesize about *why* - the
        # pattern (that postponement is recurring) still stands, but no
        # explanation is offered where none is supported (§2's own
        # "possible explanations: only where supported").
        return ()
    pattern = InferredPattern(
        statement=f"{len(items)} activities in this category were postponed, with a stated reason in {len(reasons)} case(s).",
        supporting_facts=facts,
    )
    return (
        Hypothesis(
            statement="The original time estimates for this category may be consistently optimistic, "
            "given the recurring postponement.",
            explains=pattern,
        ),
    )


def detect_estimation_accuracy(
    evidence: tuple[PatternEvidenceItem, ...], config: PatternDetectionConfig, pattern_id: str
) -> Pattern | None:
    """§6: compare estimated vs actual hours - only over items where both
    are actually present (§17's own "missing duration data handled
    safely" requirement: items without both values are silently excluded
    from the comparison, never treated as a zero or an error)."""
    comparable = [item for item in evidence if item.estimated_hours is not None and item.actual_hours is not None]
    if len(comparable) < config.min_observations:
        return None

    total_estimated = sum(item.estimated_hours for item in comparable)
    total_actual = sum(item.actual_hours for item in comparable)
    avg_estimated = total_estimated / len(comparable)
    avg_actual = total_actual / len(comparable)
    ratio = (avg_actual / avg_estimated) if avg_estimated else None

    start, end = _window(tuple(comparable))
    statement = (
        f"Across {len(comparable)} comparable activities between {start} and {end}, "
        f"estimated time averaged {avg_estimated:.1f}h and actual time averaged {avg_actual:.1f}h."
    )
    facts = tuple(
        ObservedFact(
            statement=f'"{item.activity_description}": estimated {item.estimated_hours:.1f}h, actual {item.actual_hours:.1f}h',
            evidence_ref=f"{item.observation_date}:{item.activity_description}",
        )
        for item in comparable
    )
    confidence = calculate_confidence(len(comparable), config)

    hypotheses: tuple[Hypothesis, ...] = ()
    if ratio is not None and ratio >= config.estimation_ratio_notable_threshold:
        pattern = InferredPattern(
            statement=f"Actual time for this work has averaged approximately {ratio:.1f}x the planned time.",
            supporting_facts=facts,
        )
        # Never auto-concluded WHY (§6) - every candidate explanation is
        # offered as one of several, never asserted.
        hypotheses = (
            Hypothesis(
                statement="This may reflect underestimation, interruptions during the work, "
                "unaccounted task complexity, or scope changes after planning - the evidence does not "
                "distinguish between these.",
                explains=pattern,
            ),
        )

    return Pattern(
        pattern_id=pattern_id,
        pattern_type=PatternType.ESTIMATION_ACCURACY,
        observation_window_start=start,
        observation_window_end=end,
        evidence=tuple(comparable),
        observed_facts=facts,
        pattern_statement=statement,
        confidence=confidence,
        possible_hypotheses=hypotheses,
    )


def detect_recurring_blockers(
    evidence: tuple[PatternEvidenceItem, ...], config: PatternDetectionConfig, pattern_id: str
) -> Pattern | None:
    """§7: distinguishes "blocked once" from "this class of work is
    repeatedly blocked by this class of dependency" - grouped by a
    keyword-derived blocker category from the stated reason, not by
    activity category (the dependency, not the task, is what recurs)."""
    blocked = [item for item in evidence if item.status == "blocked" and item.stated_reason]
    by_blocker: dict[str, list[PatternEvidenceItem]] = {}
    for item in blocked:
        by_blocker.setdefault(_blocker_category(item.stated_reason), []).append(item)

    best_blocker, best_items = max(by_blocker.items(), key=lambda kv: len(kv[1]), default=(None, []))
    if best_blocker is None or len(best_items) < config.min_observations:
        return None

    start, end = _window(tuple(best_items))
    statement = (
        f'A "{best_blocker}" blocker recurred {len(best_items)} times between {start} and {end}, '
        f"across: " + ", ".join(f'"{item.activity_description}"' for item in best_items)
    )
    facts = _facts_from_items(tuple(best_items))
    pattern = InferredPattern(statement=f'This class of work has repeatedly depended on "{best_blocker}".', supporting_facts=facts)
    hypotheses = (
        Hypothesis(statement=f'"{best_blocker}"-type dependencies may need to be resolved earlier, before work in this category begins.', explains=pattern),
    )

    return Pattern(
        pattern_id=pattern_id,
        pattern_type=PatternType.RECURRING_BLOCKER,
        observation_window_start=start,
        observation_window_end=end,
        evidence=tuple(best_items),
        observed_facts=facts,
        pattern_statement=statement,
        confidence=calculate_confidence(len(best_items), config),
        possible_hypotheses=hypotheses,
    )


def _blocker_category(reason: str) -> str:
    lowered = reason.lower()
    if "meeting" in lowered:
        return "meetings"
    if "waiting on" in lowered or "depend" in lowered:
        return "dependency on another person"
    if "unclear" in lowered or "requirement" in lowered:
        return "unclear requirements"
    if "information" in lowered or "info" in lowered:
        return "missing information"
    if "time" in lowered:
        return "insufficient time"
    if "priorit" in lowered:
        return "competing priorities"
    return "other"


def detect_priority_changes(
    evidence: tuple[PatternEvidenceItem, ...], config: PatternDetectionConfig, pattern_id: str
) -> Pattern | None:
    """§8: adaptive planning is not failure. Distinguishes
    externally-triggered supersessions from other ones and states the
    ratio honestly, exactly matching the spec's own worked example
    ("changed on four of six days, but three changes were triggered by
    higher-priority external commitments")."""
    superseded = [item for item in evidence if item.status == "superseded"]
    if len(superseded) < config.min_observations:
        return None

    external = [item for item in superseded if any(marker in item.stated_reason.lower() for marker in _EXTERNAL_TRIGGER_MARKERS)]
    start, end = _window(tuple(superseded))
    statement = (
        f"Priorities changed on {len(superseded)} day(s) between {start} and {end}; "
        f"{len(external)} of those changes were triggered by a stated higher-priority external commitment."
    )
    facts = _facts_from_items(tuple(superseded))
    confidence = calculate_confidence(len(superseded), config)

    hypotheses: tuple[Hypothesis, ...] = ()
    if external and len(external) == len(superseded):
        pattern = InferredPattern(statement="Every priority change in this window had an external, stated trigger.", supporting_facts=facts)
        hypotheses = (Hypothesis(statement="This appears to be adaptive, responsive planning rather than plan abandonment.", explains=pattern),)

    return Pattern(
        pattern_id=pattern_id,
        pattern_type=PatternType.PRIORITY_CHANGE,
        observation_window_start=start,
        observation_window_end=end,
        evidence=tuple(superseded),
        observed_facts=facts,
        pattern_statement=statement,
        confidence=confidence,
        possible_hypotheses=hypotheses,
    )


def detect_completion_patterns(
    evidence: tuple[PatternEvidenceItem, ...], config: PatternDetectionConfig, pattern_id: str
) -> Pattern | None:
    """§9: category-level completion rates - the only completion
    correlate this data model can honestly support today (no time-of-day
    or session-fragmentation data exists anywhere in Personal OS's model;
    claiming otherwise would be fabricated, not detected). Uses
    "appears associated with," never "causes" (§9's own explicit
    instruction)."""
    by_category: dict[str, list[PatternEvidenceItem]] = {}
    for item in evidence:
        by_category.setdefault(item.activity_category, []).append(item)

    notable: list[tuple[str, list[PatternEvidenceItem], float]] = []
    for category, items in by_category.items():
        if len(items) < config.min_observations:
            continue
        completed = [item for item in items if item.status == "completed"]
        rate = len(completed) / len(items)
        if rate >= _COMPLETION_RATE_NOTABLE:
            notable.append((category, items, rate))

    if not notable:
        return None

    best_category, best_items, best_rate = max(notable, key=lambda entry: entry[2])
    start, end = _window(tuple(best_items))
    statement = (
        f'"{best_category}" activities appear associated with reliable completion: '
        f"{best_rate:.0%} completed across {len(best_items)} observations between {start} and {end}."
    )
    facts = _facts_from_items(tuple(best_items))

    return Pattern(
        pattern_id=pattern_id,
        pattern_type=PatternType.COMPLETION_PATTERN,
        observation_window_start=start,
        observation_window_end=end,
        evidence=tuple(best_items),
        observed_facts=facts,
        pattern_statement=statement,
        confidence=calculate_confidence(len(best_items), config),
        possible_hypotheses=(),
    )


ALL_DETECTORS = (
    detect_repeated_postponement,
    detect_estimation_accuracy,
    detect_recurring_blockers,
    detect_priority_changes,
    detect_completion_patterns,
)


def detect_all(
    evidence: tuple[PatternEvidenceItem, ...], config: PatternDetectionConfig, pattern_id_factory
) -> tuple[Pattern, ...]:
    """Runs every detector against the same evidence - deterministic,
    same evidence in, same set of Patterns out (§18)."""
    patterns = []
    for detector in ALL_DETECTORS:
        pattern = detector(evidence, config, pattern_id_factory())
        if pattern is not None:
            patterns.append(pattern)
    return tuple(patterns)
