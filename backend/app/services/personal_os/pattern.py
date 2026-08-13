"""Pattern (P3 §10) - the durable record of one multi-day reasoning
chain: which evidence was gathered, what pattern it supports, what
confidence that pattern deserves, what hypothesis (if any) explains it,
what recommendation (if any) responds to it, and what the user said about
all of it.

Pattern is layered ON TOP OF reasoning.py's existing epistemic types
(ObservedFact, InferredPattern, Hypothesis, GrowthRecommendation), never
a competitor to them: reasoning.py's types are the ephemeral, structural
distinction between fact/pattern/explanation/hypothesis/recommendation;
Pattern is the durable, STATUS-TRACKED record of one such chain, with the
identity, lifecycle, and timestamps reasoning.py's own types deliberately
never carried (they are pure value objects, constructed fresh each time;
nothing about them needed a status before P3 gave a Pattern a lifecycle
to track).

PatternEvidenceItem is the raw material a detector gathers before
constructing a reasoning.py ObservedFact from it - dates, categories,
estimates, reasons, outcomes (P3 §5's own required evidence fields),
always traceable back to the specific DailyIntent/EveningReflection dates
it came from.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from app.services.personal_os.reasoning import GrowthRecommendation, Hypothesis, ObservedFact
from app.services.personal_os.shared.types import Confidence, ExperimentStatus, PatternStatus, PatternType


@dataclass(frozen=True)
class PatternEvidenceItem:
    """One day's own contribution to a pattern - never just a count.
    activity_category is PlannedActivity.focus_area when the caller set
    it, or a heuristic category derived from the description otherwise
    (pattern_detectors.py's own _categorize()) - always present, never
    None, so grouping "similar" activities never silently drops one for
    lacking a category."""

    observation_date: date
    activity_description: str
    activity_category: str
    status: str
    estimated_hours: float | None = None
    actual_hours: float | None = None
    stated_reason: str = ""

    def __post_init__(self) -> None:
        if not self.activity_description:
            raise ValueError("PatternEvidenceItem.activity_description is required")


@dataclass(frozen=True)
class Pattern:
    """Everything §10 requires, at minimum. Frozen and never mutated in
    place once created - a status change or a user response is a new
    Pattern (same pattern_id, new updated_at), matching every other
    durable Personal OS record's own append-only convention (see
    pattern_repository.py's own save() semantics)."""

    pattern_id: str
    pattern_type: PatternType
    observation_window_start: date
    observation_window_end: date
    evidence: tuple[PatternEvidenceItem, ...]
    observed_facts: tuple[ObservedFact, ...]
    pattern_statement: str
    confidence: Confidence
    possible_hypotheses: tuple[Hypothesis, ...] = field(default_factory=tuple)
    user_interpretation: str = ""
    recommendation: GrowthRecommendation | None = None
    status: PatternStatus = PatternStatus.OBSERVED
    supersedes_pattern_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.pattern_statement:
            raise ValueError("Pattern.pattern_statement is required")
        if not isinstance(self.evidence, tuple):
            object.__setattr__(self, "evidence", tuple(self.evidence))
        if not isinstance(self.observed_facts, tuple):
            object.__setattr__(self, "observed_facts", tuple(self.observed_facts))
        if not isinstance(self.possible_hypotheses, tuple):
            object.__setattr__(self, "possible_hypotheses", tuple(self.possible_hypotheses))
        if self.observation_window_start > self.observation_window_end:
            raise ValueError("Pattern.observation_window_start must not be after observation_window_end")

    @property
    def observation_count(self) -> int:
        """Derived, never stored redundantly - always exactly
        len(evidence), so this can never drift from the evidence it
        counts (a real risk if this were its own settable field)."""
        return len(self.evidence)


@dataclass(frozen=True)
class Experiment:
    """A small, optional learning experiment responding to one Pattern's
    own recommendation (P3 §13) - never mandatory; most Patterns will
    never have one. Observe -> Adjust -> Measure, made concrete: what
    changes (adjustment), for how long (review_date), and what specifically
    gets remeasured (measurement_plan) to answer the hypothesis."""

    experiment_id: str
    pattern_id: str
    hypothesis_statement: str
    adjustment: str
    measurement_plan: str
    started_on: date
    review_date: date | None = None
    status: ExperimentStatus = ExperimentStatus.PROPOSED
    review_outcome: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.hypothesis_statement:
            raise ValueError("Experiment.hypothesis_statement is required")
        if not self.adjustment:
            raise ValueError("Experiment.adjustment is required")
        if not self.measurement_plan:
            raise ValueError("Experiment.measurement_plan is required")
