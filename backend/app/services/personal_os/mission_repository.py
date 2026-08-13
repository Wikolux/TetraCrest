"""MissionRepository (P5 §15) - mirrors ExperimentRepository's own shape:
keyed by mission_id (a user may have many concurrent or historical
missions), append-only, full history preserved."""

from abc import ABC, abstractmethod

from app.services.personal_os.mission import Mission
from app.services.personal_os.shared.types import MissionStatus

ACTIVE_MISSION_STATUSES = (MissionStatus.DRAFT, MissionStatus.ACTIVE, MissionStatus.PAUSED)


class MissionRepository(ABC):
    @abstractmethod
    def save(self, mission: Mission, *, organization_id: int, user_id: int) -> Mission:
        """Persist a new Mission, or a new version of one that already
        exists (same mission_id), and return it with mission_id
        populated if it wasn't already."""
        raise NotImplementedError

    @abstractmethod
    def get_latest(self, *, organization_id: int, user_id: int, mission_id: str) -> Mission | None:
        raise NotImplementedError

    @abstractmethod
    def get_history(self, *, organization_id: int, user_id: int, mission_id: str) -> tuple[Mission, ...]:
        """Every version of one mission, oldest first - never
        overwritten (§15's own "a mission must preserve history")."""
        raise NotImplementedError

    @abstractmethod
    def list_active(self, *, organization_id: int, user_id: int) -> tuple[Mission, ...]:
        """The latest version of every mission not yet COMPLETED or
        CANCELLED."""
        raise NotImplementedError


class InMemoryMissionRepository(MissionRepository):
    def __init__(self) -> None:
        self._by_key: dict[tuple[int, int, str], list[Mission]] = {}
        self._next_id = 1

    def save(self, mission: Mission, *, organization_id: int, user_id: int) -> Mission:
        from dataclasses import replace

        stored = replace(mission, mission_id=str(self._next_id)) if not mission.mission_id else mission
        if not mission.mission_id:
            self._next_id += 1
        key = (organization_id, user_id, stored.mission_id)
        self._by_key.setdefault(key, []).append(stored)
        return stored

    def get_latest(self, *, organization_id: int, user_id: int, mission_id: str) -> Mission | None:
        versions = self._by_key.get((organization_id, user_id, mission_id))
        return versions[-1] if versions else None

    def get_history(self, *, organization_id: int, user_id: int, mission_id: str) -> tuple[Mission, ...]:
        return tuple(self._by_key.get((organization_id, user_id, mission_id), ()))

    def list_active(self, *, organization_id: int, user_id: int) -> tuple[Mission, ...]:
        active = []
        for (org_id, uid, _mission_id), versions in self._by_key.items():
            if org_id != organization_id or uid != user_id or not versions:
                continue
            latest = versions[-1]
            if latest.status in ACTIVE_MISSION_STATUSES:
                active.append(latest)
        return tuple(sorted(active, key=lambda m: m.created_at))
