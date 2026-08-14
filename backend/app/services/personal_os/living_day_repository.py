"""DayEventRepository (P6.1) - an append-only event log, one entry per
real thing that happened during a day, keyed by (organization_id,
user_id, day_date). Deliberately NOT shaped like PatternRepository/
ExperimentRepository (keyed by a single evolving entity, "latest version
wins"): a day is a sequence of many small, independent facts, not one
entity with one current status, so this repository never overwrites or
supersedes - append() only ever adds a new row, and list_for_day()
returns the complete sequence living_day.reconstruct() folds over.

sequence numbers are assigned by the repository itself, not the caller -
the same "id assigned at save time if not already set" convention every
other Personal OS repository already follows (PatternRepository.save(),
ExperimentRepository.save(), ...), applied here to strict append order
instead of identity, so reconstruct() never depends on wall-clock
timestamp precision to order two events recorded in the same instant."""

from abc import ABC, abstractmethod
from datetime import date

from app.services.personal_os.living_day import DayEvent


class DayEventRepository(ABC):
    @abstractmethod
    def append(self, event: DayEvent, *, organization_id: int, user_id: int, day_date: date) -> DayEvent:
        """Persist a new event for one day, assigning it the next
        sequence number in that day's own append-only log. Events are
        never edited, replaced, or deleted."""
        raise NotImplementedError

    @abstractmethod
    def list_for_day(self, *, organization_id: int, user_id: int, day_date: date) -> tuple[DayEvent, ...]:
        """Every event recorded for one day, in the order they were
        appended - the complete history living_day.reconstruct() folds
        into the current LivingDayState."""
        raise NotImplementedError


class InMemoryDayEventRepository(DayEventRepository):
    def __init__(self) -> None:
        self._by_key: dict[tuple[int, int, date], list[DayEvent]] = {}
        self._next_sequence: dict[tuple[int, int, date], int] = {}
        self._next_id = 1

    def append(self, event: DayEvent, *, organization_id: int, user_id: int, day_date: date) -> DayEvent:
        from dataclasses import replace

        key = (organization_id, user_id, day_date)
        sequence = self._next_sequence.get(key, 0) + 1
        self._next_sequence[key] = sequence

        stored = replace(event, sequence=sequence, event_id=event.event_id or str(self._next_id))
        if not event.event_id:
            self._next_id += 1
        self._by_key.setdefault(key, []).append(stored)
        return stored

    def list_for_day(self, *, organization_id: int, user_id: int, day_date: date) -> tuple[DayEvent, ...]:
        return tuple(self._by_key.get((organization_id, user_id, day_date), ()))
