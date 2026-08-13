"""DailyIntentRepository - how Personal OS persists its own orchestration
state.

Deliberately not AgentMemory: DailyIntent is structured Application state
Personal OS itself owns (a form the user fills out each morning), not a
semantically-retrievable fact a Capability Pack specialist reasons over -
routing it through AgentMemory would mean minting a new memory_type
namespace for it, which the Application Layer Definition
(VERSION_1_PLATFORM_BASELINE.md) explicitly says an Application does not
do. This mirrors how the rest of this backend already separates
structured, repository-backed domain data (BaseRepository) from the AI
Operating System's own semantic Memory Framework - Personal OS's own
state belongs with the former, not the latter.

organization_id/user_id are passed alongside DailyIntent, never stored
inside it - the same "identity travels with the call, not inside the
domain object" convention PersonalMemoryService.remember_goal() etc.
already establish (Coding_Standards.md).

InMemoryDailyIntentRepository is this phase's real, usable
implementation - not a test-only fake - explicitly non-durable across
process restarts. A database-backed implementation satisfying the same
interface is this milestone's own named, deferred next step (see the
completion report's architecture mapping), not built here.
"""

from abc import ABC, abstractmethod
from dataclasses import replace
from datetime import date

from app.services.personal_os.daily_intent import DailyIntent


class DailyIntentRepository(ABC):
    @abstractmethod
    def save(self, intent: DailyIntent, *, organization_id: int, user_id: int) -> DailyIntent:
        """Persist a new DailyIntent (or a new version superseding a
        prior one) and return it, with intent_id populated."""
        raise NotImplementedError

    @abstractmethod
    def get_for_date(self, *, organization_id: int, user_id: int, intent_date: date) -> DailyIntent | None:
        """The current (most recently saved) DailyIntent for one user on
        one date, or None if none exists yet."""
        raise NotImplementedError

    @abstractmethod
    def get_latest_before(self, *, organization_id: int, user_id: int, before: date) -> DailyIntent | None:
        """The most recent DailyIntent strictly before `before` - used to
        find "yesterday's plan" without assuming it was exactly one
        calendar day prior (a user may skip a day)."""
        raise NotImplementedError


class InMemoryDailyIntentRepository(DailyIntentRepository):
    """Process-local reference implementation. Keyed by
    (organization_id, user_id, intent_date) -> list of DailyIntent
    versions (append-only, oldest first), so get_for_date always returns
    the latest version for that date and history is never discarded."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[int, int, date], list[DailyIntent]] = {}
        self._next_id = 1

    def save(self, intent: DailyIntent, *, organization_id: int, user_id: int) -> DailyIntent:
        stored = replace(intent, intent_id=str(self._next_id)) if not intent.intent_id else intent
        self._next_id += 1 if not intent.intent_id else 0
        key = (organization_id, user_id, stored.intent_date)
        self._by_key.setdefault(key, []).append(stored)
        return stored

    def get_for_date(self, *, organization_id: int, user_id: int, intent_date: date) -> DailyIntent | None:
        versions = self._by_key.get((organization_id, user_id, intent_date))
        return versions[-1] if versions else None

    def get_latest_before(self, *, organization_id: int, user_id: int, before: date) -> DailyIntent | None:
        candidates = [
            versions[-1]
            for (org_id, uid, intent_date), versions in self._by_key.items()
            if org_id == organization_id and uid == user_id and intent_date < before and versions
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda intent: intent.intent_date)
