"""Experiment (P3 §13, extended P4): the durable, status-tracked record
of one small, explicit, user-approved learning cycle - Propose -> Approve
-> Activate -> Review -> Decide, per P4's own build spec.

`Experiment` moved here from pattern.py (P3) now that it is genuinely its
own concern with its own baseline/measurement/comparison model, rather
than a small appendix to Pattern's own module - Pattern still owns
detection; Experiment owns measurement. The two are linked only by
`Experiment.pattern_id`, never by direct object nesting, so an
Experiment's own lifecycle never has to reach back into Pattern's own
persisted state to make sense on its own.

ExperimentBaseline/ExperimentMeasurement are structurally identical in
shape (metric, category, period, value, observation_count) but kept as
two distinct types rather than one reused type: a baseline is fixed at
proposal time and never recomputed; a measurement is taken fresh at
review time. Conflating them risks a caller accidentally comparing a
measurement against itself, or silently overwriting a baseline - keeping
them distinct types makes that a type error, not a runtime bug.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from app.services.personal_os.shared.types import Confidence, ExperimentOutcome, ExperimentStatus, ExperimentUserDecision


@dataclass(frozen=True)
class ExperimentBaseline:
    """What the metric looked like before the experiment started (P4 §5)
    - always computed from real, persisted evidence at proposal time,
    never fabricated. observation_count is the number of category-
    matching evidence items the value was computed from; a baseline with
    observation_count=0 must never be constructed (experiment_measurement
    .build_baseline() returns None rather than a zero-evidence baseline -
    see its own docstring)."""

    metric: str
    category: str
    period_start: date
    period_end: date
    value: float
    observation_count: int

    def __post_init__(self) -> None:
        if not self.metric:
            raise ValueError("ExperimentBaseline.metric is required")
        if not self.category:
            raise ValueError("ExperimentBaseline.category is required")
        if self.observation_count <= 0:
            raise ValueError("ExperimentBaseline.observation_count must be positive - a baseline requires real evidence")
        if self.period_start > self.period_end:
            raise ValueError("ExperimentBaseline.period_start must not be after period_end")


@dataclass(frozen=True)
class ExperimentMeasurement:
    """The same metric, recomputed over the experiment's own measurement
    period at review time (P4 §8) - never over a period the caller
    silently changed after the fact (§8's own explicit instruction)."""

    metric: str
    category: str
    period_start: date
    period_end: date
    value: float
    observation_count: int

    def __post_init__(self) -> None:
        if not self.metric:
            raise ValueError("ExperimentMeasurement.metric is required")
        if not self.category:
            raise ValueError("ExperimentMeasurement.category is required")
        if self.observation_count < 0:
            raise ValueError("ExperimentMeasurement.observation_count must not be negative")
        if self.period_start > self.period_end:
            raise ValueError("ExperimentMeasurement.period_start must not be after period_end")


@dataclass(frozen=True)
class ExperimentComparison:
    """The deterministic result of comparing a measurement against its
    baseline (P4 §9-§11) - absolute_change and relative_change are plain
    arithmetic, outcome/confidence are rule-based classifications, and
    observation_statement is factual ("Postponements decreased by 75%
    during the experiment period"), never causal ("caused a 75%
    improvement") - §9's own explicit distinction. relative_change is
    None when baseline.value == 0 (division is undefined, not zero)."""

    baseline: ExperimentBaseline
    measurement: ExperimentMeasurement
    absolute_change: float
    relative_change: float | None
    outcome: ExperimentOutcome
    confidence: Confidence
    observation_statement: str

    def __post_init__(self) -> None:
        if not self.observation_statement:
            raise ValueError("ExperimentComparison.observation_statement is required")


@dataclass(frozen=True)
class Experiment:
    """A small, optional learning experiment responding to one Pattern's
    own recommendation - never mandatory; most Patterns will never have
    one. Frozen and append-only like every other durable Personal OS
    record: a lifecycle transition (approve, activate, review, decide) is
    a new Experiment saved under the SAME experiment_id, never a mutation
    - ExperimentRepository.get_history() returns every version, so
    nothing about a prior review or decision is ever lost (P4 §16)."""

    experiment_id: str
    pattern_id: str
    hypothesis_statement: str
    adjustment: str
    measurement_plan: str
    baseline: ExperimentBaseline
    started_on: date
    review_date: date | None = None
    status: ExperimentStatus = ExperimentStatus.PROPOSED
    comparison: ExperimentComparison | None = None
    review_narrative: str = ""
    decision: ExperimentUserDecision | None = None
    decision_reason: str = ""
    # Repurposed from its P3 shape: the deterministic, factual one-line
    # summary of the comparison (ExperimentComparison.observation_statement),
    # kept here too for a quick-glance summary without unpacking
    # `comparison` - never a second, independent claim about the outcome.
    review_outcome: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.hypothesis_statement:
            raise ValueError("Experiment.hypothesis_statement is required")
        if not self.adjustment:
            raise ValueError("Experiment.adjustment is required")
        if not self.measurement_plan:
            raise ValueError("Experiment.measurement_plan is required")
        if self.baseline is None:
            raise ValueError("Experiment.baseline is required - P4 §5: every measurable experiment must preserve its baseline")
