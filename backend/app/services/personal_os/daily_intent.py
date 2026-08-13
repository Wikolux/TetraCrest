"""DailyIntent - the durable representation of "what kind of day is this,
and why" (§4 of the Personal OS build spec).

Every field that can come from a different place (yesterday's plan, a
fresh user statement, a heuristic guess) carries its own IntentSource/
Confidence via IntentField, rather than the whole record sharing one
blanket provenance - a caller can tell exactly which parts of today's
intent are carried forward versus freshly stated versus guessed.

Frozen and append-only, matching every other durable domain object on
this platform (CP-01/CP-02's own convention): PersonalOSApplication
never edits a DailyIntent in place once the day has started - a mid-day
change to intent is a new DailyIntent (same date, later updated_at),
referencing the one it supersedes via supersedes_intent_id, never a
mutation of the original.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from app.services.personal_os.shared.types import Confidence, DayType, IntentSource


@dataclass(frozen=True)
class IntentField:
    """One piece of a DailyIntent, with its own provenance - the
    "confidence/source of each item" requirement from §4, applied
    per-field rather than once for the whole record."""

    value: str
    source: IntentSource
    confidence: Confidence

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("IntentField.value is required")


@dataclass(frozen=True)
class PlannedActivity:
    """One activity the user intends to do today - deliberately not
    "a task," since Personal OS's own DailyIntent is about intention, not
    execution tracking (that is Task Reconciliation's job, the next day,
    against whatever activities were actually planned).

    estimated_hours (P3) is optional and additive - P1/P2 never set it,
    and every existing caller still constructs a valid PlannedActivity
    without it. It exists specifically so Estimation Accuracy pattern
    detection (P3 §6) has real data to compare against actual_hours
    (reconciliation.py's own ReconciliationEvidence) - before this field
    existed, no duration data existed anywhere in Personal OS's model at
    all, so "compare planned vs actual" could not have been honestly
    implemented."""

    description: str
    focus_area: str = ""
    deadline: date | None = None
    estimated_hours: float | None = None

    def __post_init__(self) -> None:
        if not self.description:
            raise ValueError("PlannedActivity.description is required")
        if self.estimated_hours is not None and self.estimated_hours <= 0:
            raise ValueError("PlannedActivity.estimated_hours must be positive when given")


@dataclass(frozen=True)
class DailyIntent:
    """Everything §4 requires, at minimum. `stated_intention` is the
    user's own words (or the carried-over summary, if the user simply
    continued yesterday's plan) - never rewritten or paraphrased away."""

    intent_date: date
    stated_intention: str
    day_type: DayType
    continuation_of_date: date | None = None
    new_priorities: tuple[IntentField, ...] = field(default_factory=tuple)
    planned_activities: tuple[PlannedActivity, ...] = field(default_factory=tuple)
    is_rest_day: bool = False
    focus_areas: tuple[str, ...] = field(default_factory=tuple)
    known_constraints: tuple[str, ...] = field(default_factory=tuple)
    deadlines: tuple[str, ...] = field(default_factory=tuple)
    scheduling_preferences: tuple[str, ...] = field(default_factory=tuple)
    user_provided_changes: tuple[str, ...] = field(default_factory=tuple)
    supersedes_intent_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    intent_id: str = field(default_factory=lambda: "")

    def __post_init__(self) -> None:
        if not self.stated_intention:
            raise ValueError("DailyIntent.stated_intention is required")
        for name in (
            "new_priorities",
            "planned_activities",
            "focus_areas",
            "known_constraints",
            "deadlines",
            "scheduling_preferences",
            "user_provided_changes",
        ):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
        if self.is_rest_day and self.day_type != DayType.REST:
            raise ValueError("DailyIntent.is_rest_day=True requires day_type=DayType.REST")
