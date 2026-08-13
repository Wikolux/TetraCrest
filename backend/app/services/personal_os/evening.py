"""Evening reflection contract (P1 §9) and its P2 implementation.

EveningReflection is deliberately shaped to be exactly what
reconciliation.py's ReconciliationEvidence needs (§6) and what
reasoning.py's ObservedFact needs (§10) - the evening flow's whole job is
producing the evidence tomorrow morning's reconciliation and this
platform's own pattern-detection consume, not a free-form journal entry.

EveningReflectionRepository now mirrors DailyIntentRepository's own
shape exactly (repository.py): an ABC, a real in-memory reference
implementation, and - for durable storage -
app/services/personal_os/sql_repository.py's SqlEveningReflectionRepository.
Same reasoning as DailyIntentRecord: Application-owned structured state,
never routed through AgentMemory, never a new memory_type namespace.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from app.services.personal_os.reconciliation import ReconciliationEvidence, ReconciliationRecord


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


class EveningReflectionRepository(ABC):
    """The same shape DailyIntentRepository establishes (repository.py).
    save() takes the already-reconciled ReconciliationRecords alongside
    the reflection itself, so "what did I plan / what happened / why" all
    stay answerable from one saved reflection (P2 §5) without needing to
    recompute reconciliation from raw evidence on every read."""

    @abstractmethod
    def save(
        self,
        reflection: EveningReflection,
        reconciliations: tuple[ReconciliationRecord, ...],
        *,
        organization_id: int,
        user_id: int,
        daily_intent_id: str | None,
    ) -> EveningReflection:
        raise NotImplementedError

    @abstractmethod
    def get_for_date(self, *, organization_id: int, user_id: int, reflection_date: date) -> EveningReflection | None:
        raise NotImplementedError

    @abstractmethod
    def get_reconciliations_for_date(
        self, *, organization_id: int, user_id: int, reflection_date: date
    ) -> tuple[ReconciliationRecord, ...]:
        """The reconciled outcome (§5) for a date's reflection - part of
        the contract, not an implementation extra, since
        MorningInteractionFlow needs it (tomorrow-context, P2 §8) without
        depending on a concrete repository type."""
        raise NotImplementedError

    @abstractmethod
    def list_reconciliations_range(
        self, *, organization_id: int, user_id: int, start: date, end: date
    ) -> tuple[tuple[date, ReconciliationRecord], ...]:
        """Every reconciled outcome across [start, end], each paired with
        the date it came from - added in P3 for multi-day pattern
        detection (pattern_evidence.py). The date pairing matters:
        ReconciliationRecord itself carries no date, so a flat tuple of
        records alone would lose exactly the "when" a pattern detector
        needs to build its own observation_window and dated evidence."""
        raise NotImplementedError


class InMemoryEveningReflectionRepository(EveningReflectionRepository):
    """Process-local reference implementation, mirroring
    InMemoryDailyIntentRepository's own shape exactly (repository.py) -
    one reflection per (organization_id, user_id, reflection_date), never
    edited after being saved."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[int, int, date], EveningReflection] = {}
        self._reconciliations_by_key: dict[tuple[int, int, date], tuple[ReconciliationRecord, ...]] = {}

    def save(
        self,
        reflection: EveningReflection,
        reconciliations: tuple[ReconciliationRecord, ...],
        *,
        organization_id: int,
        user_id: int,
        daily_intent_id: str | None,
    ) -> EveningReflection:
        key = (organization_id, user_id, reflection.reflection_date)
        self._by_key[key] = reflection
        self._reconciliations_by_key[key] = reconciliations
        return reflection

    def get_for_date(self, *, organization_id: int, user_id: int, reflection_date: date) -> EveningReflection | None:
        return self._by_key.get((organization_id, user_id, reflection_date))

    def get_reconciliations_for_date(
        self, *, organization_id: int, user_id: int, reflection_date: date
    ) -> tuple[ReconciliationRecord, ...]:
        return self._reconciliations_by_key.get((organization_id, user_id, reflection_date), ())

    def list_reconciliations_range(
        self, *, organization_id: int, user_id: int, start: date, end: date
    ) -> tuple[tuple[date, ReconciliationRecord], ...]:
        pairs = []
        for (org_id, uid, reflection_date), records in sorted(self._reconciliations_by_key.items(), key=lambda kv: kv[0][2]):
            if org_id == organization_id and uid == user_id and start <= reflection_date <= end:
                pairs.extend((reflection_date, record) for record in records)
        return tuple(pairs)
