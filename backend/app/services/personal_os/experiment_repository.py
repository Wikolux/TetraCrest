"""ExperimentRepository (P4 §16) - mirrors PatternRepository's own shape
exactly: an ABC, a real in-memory reference implementation here, and a
durable SqlExperimentRepository in sql_repository.py.

Experiments are Application-owned structured state, the identical
architectural precedent P1-P3 already established: never routed through
AgentMemory, never a new memory_type namespace.

Unlike Pattern (keyed by pattern_type, since there is meaningfully only
one "current" pattern of each type per user), an Experiment is keyed by
its own experiment_id: a user may have many concurrent or historical
experiments, and every lifecycle transition (approve, activate, review,
decide) is a new version saved under that SAME experiment_id, never a
mutation - get_history() returns every version in order, so nothing
about a prior review or decision is ever lost (§16's own explicit
requirement)."""

from abc import ABC, abstractmethod
from datetime import date

from app.services.personal_os.experiment import Experiment
from app.services.personal_os.shared.types import ExperimentStatus

ACTIVE_EXPERIMENT_STATUSES = (
    ExperimentStatus.PROPOSED,
    ExperimentStatus.APPROVED,
    ExperimentStatus.ACTIVE,
    ExperimentStatus.READY_FOR_REVIEW,
    ExperimentStatus.REVIEWED,
)


class ExperimentRepository(ABC):
    @abstractmethod
    def save(self, experiment: Experiment, *, organization_id: int, user_id: int) -> Experiment:
        """Persist a new Experiment, or a new lifecycle version of one
        that already exists (same experiment_id), and return it with
        experiment_id populated if it wasn't already."""
        raise NotImplementedError

    @abstractmethod
    def get_latest(self, *, organization_id: int, user_id: int, experiment_id: str) -> Experiment | None:
        """The current (most recently saved) version of one experiment."""
        raise NotImplementedError

    @abstractmethod
    def get_history(self, *, organization_id: int, user_id: int, experiment_id: str) -> tuple[Experiment, ...]:
        """Every version of one experiment, oldest first - the full,
        never-overwritten lifecycle (§16): original proposal, approval,
        activation, review, and final decision, each independently
        retrievable."""
        raise NotImplementedError

    @abstractmethod
    def list_active(self, *, organization_id: int, user_id: int) -> tuple[Experiment, ...]:
        """The latest version of every experiment not yet in a terminal
        state (KEPT/MODIFIED/STOPPED/EXPIRED) - what a caller should
        actually consider when deciding what to surface next."""
        raise NotImplementedError

    @abstractmethod
    def list_ready_for_review(self, *, organization_id: int, user_id: int, today: date) -> tuple[Experiment, ...]:
        """Every ACTIVE experiment whose review_date has arrived, plus
        every experiment already transitioned to READY_FOR_REVIEW - the
        query §7 names ("EXPERIMENTS READY FOR REVIEW"), computed
        deterministically from persisted state, never requiring the user
        to remember on their own."""
        raise NotImplementedError


class InMemoryExperimentRepository(ExperimentRepository):
    """Process-local reference implementation - one version history per
    (organization_id, user_id, experiment_id), latest wins, nothing
    discarded, mirroring InMemoryPatternRepository's own shape exactly."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[int, int, str], list[Experiment]] = {}
        self._next_id = 1

    def save(self, experiment: Experiment, *, organization_id: int, user_id: int) -> Experiment:
        from dataclasses import replace

        stored = replace(experiment, experiment_id=str(self._next_id)) if not experiment.experiment_id else experiment
        if not experiment.experiment_id:
            self._next_id += 1
        key = (organization_id, user_id, stored.experiment_id)
        self._by_key.setdefault(key, []).append(stored)
        return stored

    def get_latest(self, *, organization_id: int, user_id: int, experiment_id: str) -> Experiment | None:
        versions = self._by_key.get((organization_id, user_id, experiment_id))
        return versions[-1] if versions else None

    def get_history(self, *, organization_id: int, user_id: int, experiment_id: str) -> tuple[Experiment, ...]:
        return tuple(self._by_key.get((organization_id, user_id, experiment_id), ()))

    def list_active(self, *, organization_id: int, user_id: int) -> tuple[Experiment, ...]:
        active = []
        for (org_id, uid, _experiment_id), versions in self._by_key.items():
            if org_id != organization_id or uid != user_id or not versions:
                continue
            latest = versions[-1]
            if latest.status in ACTIVE_EXPERIMENT_STATUSES:
                active.append(latest)
        return tuple(sorted(active, key=lambda e: e.created_at))

    def list_ready_for_review(self, *, organization_id: int, user_id: int, today: date) -> tuple[Experiment, ...]:
        ready = []
        for experiment in self.list_active(organization_id=organization_id, user_id=user_id):
            if experiment.status == ExperimentStatus.READY_FOR_REVIEW:
                ready.append(experiment)
            elif experiment.status == ExperimentStatus.ACTIVE and experiment.review_date is not None and experiment.review_date <= today:
                ready.append(experiment)
        return tuple(sorted(ready, key=lambda e: e.review_date or e.created_at.date()))
