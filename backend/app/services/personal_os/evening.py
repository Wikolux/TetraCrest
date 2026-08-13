"""Evening reflection contract (§9 of the build spec) - the shape a
future evening-reflection flow will produce and consume, defined now so
that flow is an implementation against an existing contract next
milestone, not an architecture change.

EveningReflection is deliberately shaped to be exactly what
reconciliation.py's ReconciliationEvidence needs (§6) and what
reasoning.py's ObservedFact needs (§10) - the evening flow's whole job is
producing the evidence tomorrow morning's reconciliation and this
platform's own pattern-detection consume, not a free-form journal entry.

No morning-flow-equivalent interaction logic is built this phase - only
the data contract, per §9's own "implementation may remain minimal."
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from app.services.personal_os.reconciliation import ReconciliationEvidence


@dataclass(frozen=True)
class EveningReflection:
    """One day's own account of how it actually went - always written
    the same day it reflects on, never backfilled or edited after the
    fact (append-only, matching every other durable record on this
    platform)."""

    reflection_date: date
    accomplishments: tuple[str, ...] = field(default_factory=tuple)
    evidence_by_activity_description: dict[str, ReconciliationEvidence] = field(default_factory=dict)
    unexpected_events: tuple[str, ...] = field(default_factory=tuple)
    lessons: tuple[str, ...] = field(default_factory=tuple)
    decisions: tuple[str, ...] = field(default_factory=tuple)
    worth_remembering: tuple[str, ...] = field(default_factory=tuple)
    preparation_for_tomorrow: tuple[str, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        for name in ("accomplishments", "unexpected_events", "lessons", "decisions", "worth_remembering", "preparation_for_tomorrow"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))


class EveningReflectionRepository:
    """The same shape DailyIntentRepository establishes (repository.py),
    named here as a contract only - not implemented this phase, since no
    evening flow exists yet to call it. The next milestone implements
    this against the identical InMemoryDailyIntentRepository pattern,
    not a new one."""
