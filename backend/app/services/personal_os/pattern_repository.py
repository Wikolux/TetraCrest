"""PatternRepository (P3 §10, §14) - mirrors DailyIntentRepository's own
shape exactly: an ABC, a real in-memory reference implementation here,
and a durable SqlPatternRepository in sql_repository.py.

Patterns are Application-owned structured state, the identical
architectural precedent P1 established for DailyIntent and P2 confirmed
against real durable storage for EveningReflection: never routed through
AgentMemory, never a new memory_type namespace (§14's own explicit
instruction) - a Pattern is Personal OS's own operational intelligence
about the user's own multi-day evidence, not a Capability Pack's
semantic memory fact.

A status change or user response is a new Pattern (save() again, same
pattern_id, PatternStatus.SUPERSEDED on the prior version) - the same
append-only, never-mutated-in-place convention every durable Personal OS
record already follows (§10's own "do not store inferred patterns as
permanent truth without appropriate status").
"""

from abc import ABC, abstractmethod

from app.services.personal_os.pattern import Pattern
from app.services.personal_os.shared.types import PatternStatus, PatternType


class PatternRepository(ABC):
    @abstractmethod
    def save(self, pattern: Pattern, *, organization_id: int, user_id: int) -> Pattern:
        """Persist a new Pattern (or a new status version of one that
        already exists, via supersedes_pattern_id) and return it, with
        pattern_id populated if it wasn't already."""
        raise NotImplementedError

    @abstractmethod
    def get_latest(self, *, organization_id: int, user_id: int, pattern_type: PatternType) -> Pattern | None:
        """The current (most recently saved) Pattern of one type - never
        every version, mirroring DailyIntentRepository.get_for_date's own
        "latest version" semantics."""
        raise NotImplementedError

    @abstractmethod
    def list_active(self, *, organization_id: int, user_id: int) -> tuple[Pattern, ...]:
        """Every Pattern whose latest version is not DISMISSED or
        SUPERSEDED - what a confirmation flow should actually consider
        surfacing."""
        raise NotImplementedError


class InMemoryPatternRepository(PatternRepository):
    """Process-local reference implementation, mirroring
    InMemoryDailyIntentRepository's own shape exactly - one version
    history per (organization_id, user_id, pattern_type), latest wins,
    nothing discarded."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[int, int, PatternType], list[Pattern]] = {}
        self._next_id = 1

    def save(self, pattern: Pattern, *, organization_id: int, user_id: int) -> Pattern:
        from dataclasses import replace

        stored = replace(pattern, pattern_id=str(self._next_id)) if not pattern.pattern_id else pattern
        if not pattern.pattern_id:
            self._next_id += 1
        key = (organization_id, user_id, stored.pattern_type)
        self._by_key.setdefault(key, []).append(stored)
        return stored

    def get_latest(self, *, organization_id: int, user_id: int, pattern_type: PatternType) -> Pattern | None:
        versions = self._by_key.get((organization_id, user_id, pattern_type))
        return versions[-1] if versions else None

    def list_active(self, *, organization_id: int, user_id: int) -> tuple[Pattern, ...]:
        active = []
        for (org_id, uid, _pattern_type), versions in self._by_key.items():
            if org_id != organization_id or uid != user_id or not versions:
                continue
            latest = versions[-1]
            if latest.status not in (PatternStatus.DISMISSED, PatternStatus.SUPERSEDED):
                active.append(latest)
        return tuple(sorted(active, key=lambda p: p.created_at))
