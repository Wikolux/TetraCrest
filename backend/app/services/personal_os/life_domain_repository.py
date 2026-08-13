"""LifeDomainStateRepository (P5 §6) - mirrors PatternRepository's own
shape exactly: keyed by LifeDomain (one current state per domain, like
Pattern is keyed by PatternType), append-only, history preserved.

A status change (ACTIVE -> PAUSED -> ACTIVE) is a new LifeDomainState
saved under the same domain key, never a mutation - §6's own explicit
"must remain historically traceable" requirement, satisfied the same way
Pattern/Experiment already satisfy their own history requirements."""

from abc import ABC, abstractmethod

from app.services.personal_os.life_domain import LifeDomainState
from app.services.personal_os.shared.types import LifeDomain


class LifeDomainStateRepository(ABC):
    @abstractmethod
    def save(self, state: LifeDomainState, *, organization_id: int, user_id: int) -> LifeDomainState:
        """Persist a new LifeDomainState (or a new version of one that
        already exists) and return it, with state_id populated."""
        raise NotImplementedError

    @abstractmethod
    def get_latest(self, *, organization_id: int, user_id: int, domain: LifeDomain) -> LifeDomainState | None:
        """The current state for one domain, or None if the domain has
        never been touched - the caller should treat that as
        life_domain.default_state(domain), never as an error."""
        raise NotImplementedError

    @abstractmethod
    def get_history(self, *, organization_id: int, user_id: int, domain: LifeDomain) -> tuple[LifeDomainState, ...]:
        """Every version for one domain, oldest first - the full,
        never-overwritten transition history (§6)."""
        raise NotImplementedError

    @abstractmethod
    def list_all_latest(self, *, organization_id: int, user_id: int) -> tuple[LifeDomainState, ...]:
        """The current state of every domain that has ever been touched -
        domains never touched are simply absent, never fabricated."""
        raise NotImplementedError


class InMemoryLifeDomainStateRepository(LifeDomainStateRepository):
    def __init__(self) -> None:
        self._by_key: dict[tuple[int, int, LifeDomain], list[LifeDomainState]] = {}
        self._next_id = 1

    def save(self, state: LifeDomainState, *, organization_id: int, user_id: int) -> LifeDomainState:
        from dataclasses import replace

        stored = replace(state, state_id=str(self._next_id)) if not state.state_id else state
        if not state.state_id:
            self._next_id += 1
        key = (organization_id, user_id, stored.domain)
        self._by_key.setdefault(key, []).append(stored)
        return stored

    def get_latest(self, *, organization_id: int, user_id: int, domain: LifeDomain) -> LifeDomainState | None:
        versions = self._by_key.get((organization_id, user_id, domain))
        return versions[-1] if versions else None

    def get_history(self, *, organization_id: int, user_id: int, domain: LifeDomain) -> tuple[LifeDomainState, ...]:
        return tuple(self._by_key.get((organization_id, user_id, domain), ()))

    def list_all_latest(self, *, organization_id: int, user_id: int) -> tuple[LifeDomainState, ...]:
        latest = []
        for (org_id, uid, _domain), versions in self._by_key.items():
            if org_id == organization_id and uid == user_id and versions:
                latest.append(versions[-1])
        return tuple(sorted(latest, key=lambda s: s.domain.value))
