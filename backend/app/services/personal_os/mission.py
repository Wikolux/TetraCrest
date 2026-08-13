"""Mission (P5 §14-§17): "I want to accomplish X" - a container for
multiple tasks, research activities, decisions, deadlines, and
recommendations, never itself a single task.

AutonomyGrant is nested directly on Mission rather than given its own
top-level repository: it is inherently mission-scoped content (§20: "
Autonomy authorization should be scoped to: mission, action, duration,
conditions"), not an independent entity with its own lifecycle worth a
separate persistence path - the same "do not create every possible
field/repository" discipline §16, §28 both ask for. See autonomy.py for
the deterministic policy check that reads these grants; this module only
defines their shape.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from app.services.personal_os.shared.types import AutonomyAction, LifeDomain, MissionStatus


@dataclass(frozen=True)
class AutonomyGrant:
    """One explicit, scoped authorization (§18, §20) - never a blanket
    permission. `scope` is the user's own words describing exactly what
    this grant covers ("flights matching the agreed dates, under
    budget"), never inferred or generalized beyond that by any code in
    this package (autonomy.py's own is_authorized() matches action +
    non-expired + non-revoked only - it has no concept of "similar
    enough" scope)."""

    action: AutonomyAction
    scope: str
    granted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    conditions: tuple[str, ...] = field(default_factory=tuple)
    revoked: bool = False
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.scope:
            raise ValueError("AutonomyGrant.scope is required - authorization must be scoped, never blanket (§20)")
        if not isinstance(self.conditions, tuple):
            object.__setattr__(self, "conditions", tuple(self.conditions))


@dataclass(frozen=True)
class Mission:
    """Everything §16 requires, at minimum - consolidated the same way
    LifeDomainState's fields are: "related commitments" is
    related_commitment_ids (a reference, never a duplicated copy of
    commitment content); "current next step" is next_step, a single
    field rather than a whole sub-task list, since P5 does not build a
    second task system (§2, §26) - a Mission names its immediate next
    step in plain language; anything more structured is exactly the kind
    of task-tracking machinery this milestone explicitly defers."""

    mission_id: str
    objective: str
    status: MissionStatus = MissionStatus.DRAFT
    domain: LifeDomain | None = None
    target_date: date | None = None
    budget: str = ""
    constraints: tuple[str, ...] = field(default_factory=tuple)
    preferences: tuple[str, ...] = field(default_factory=tuple)
    related_commitment_ids: tuple[str, ...] = field(default_factory=tuple)
    autonomy_grants: tuple[AutonomyGrant, ...] = field(default_factory=tuple)
    notes: str = ""
    next_step: str = ""
    supersedes_mission_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.objective:
            raise ValueError("Mission.objective is required")
        for name in ("constraints", "preferences", "related_commitment_ids", "autonomy_grants"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
