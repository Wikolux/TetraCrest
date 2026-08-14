"""AdaptationRepository (P7.10) - mirrors ExperimentRepository's own
shape exactly: keyed by adaptation_id (a user may have many concurrent
or historical adaptations across all four scopes), append-only, full
history preserved. Application-owned structured state, the identical
architectural precedent P1-P6 already established: never routed through
AgentMemory, never a new memory_type namespace, never a second
persistence framework."""

from abc import ABC, abstractmethod

from app.services.personal_os.adaptation import Adaptation, AdaptationTarget
from app.services.personal_os.shared.types import AdaptationStatus

ACTIVE_ADAPTATION_STATUSES = (
    AdaptationStatus.PROPOSED,
    AdaptationStatus.UNDER_EVALUATION,
    AdaptationStatus.APPROVED,
    AdaptationStatus.ADOPTED,
)


class AdaptationRepository(ABC):
    @abstractmethod
    def save(self, adaptation: Adaptation, *, organization_id: int, user_id: int) -> Adaptation:
        """Persist a new Adaptation, or a new lifecycle version of one
        that already exists (same adaptation_id), and return it with
        adaptation_id populated if it wasn't already."""
        raise NotImplementedError

    @abstractmethod
    def get_latest(self, *, organization_id: int, user_id: int, adaptation_id: str) -> Adaptation | None:
        raise NotImplementedError

    @abstractmethod
    def get_history(self, *, organization_id: int, user_id: int, adaptation_id: str) -> tuple[Adaptation, ...]:
        """Every version of one adaptation, oldest first - never
        overwritten (P7.10 §13's own "do not rewrite history")."""
        raise NotImplementedError

    @abstractmethod
    def list_active(self, *, organization_id: int, user_id: int) -> tuple[Adaptation, ...]:
        """The latest version of every adaptation not yet REJECTED,
        ROLLED_BACK, or SUPERSEDED."""
        raise NotImplementedError

    @abstractmethod
    def get_adopted_for_target(self, *, organization_id: int, user_id: int, target: AdaptationTarget) -> Adaptation | None:
        """Whatever is CURRENTLY adopted for one specific scope+target -
        the key new query surface P7.10 needs that no existing repository
        provides (§13's "distinguish CURRENT / SUPERSEDED / ROLLED_BACK").
        Never more than one Adaptation should be ADOPTED for the same
        target at once - a RELEARN's own adopt() step (adaptation_flow.py)
        is what keeps this true, by superseding the predecessor in the
        same transaction as adopting its replacement."""
        raise NotImplementedError


class InMemoryAdaptationRepository(AdaptationRepository):
    def __init__(self) -> None:
        self._by_key: dict[tuple[int, int, str], list[Adaptation]] = {}
        self._next_id = 1

    def save(self, adaptation: Adaptation, *, organization_id: int, user_id: int) -> Adaptation:
        from dataclasses import replace

        stored = replace(adaptation, adaptation_id=str(self._next_id)) if not adaptation.adaptation_id else adaptation
        if not adaptation.adaptation_id:
            self._next_id += 1
        key = (organization_id, user_id, stored.adaptation_id)
        self._by_key.setdefault(key, []).append(stored)
        return stored

    def get_latest(self, *, organization_id: int, user_id: int, adaptation_id: str) -> Adaptation | None:
        versions = self._by_key.get((organization_id, user_id, adaptation_id))
        return versions[-1] if versions else None

    def get_history(self, *, organization_id: int, user_id: int, adaptation_id: str) -> tuple[Adaptation, ...]:
        return tuple(self._by_key.get((organization_id, user_id, adaptation_id), ()))

    def list_active(self, *, organization_id: int, user_id: int) -> tuple[Adaptation, ...]:
        active = []
        for (org_id, uid, _adaptation_id), versions in self._by_key.items():
            if org_id != organization_id or uid != user_id or not versions:
                continue
            latest = versions[-1]
            if latest.status in ACTIVE_ADAPTATION_STATUSES:
                active.append(latest)
        return tuple(sorted(active, key=lambda a: a.created_at))

    def get_adopted_for_target(self, *, organization_id: int, user_id: int, target: AdaptationTarget) -> Adaptation | None:
        for adaptation in self.list_active(organization_id=organization_id, user_id=user_id):
            if adaptation.status == AdaptationStatus.ADOPTED and adaptation.target == target:
                return adaptation
        return None
