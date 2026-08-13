"""Task - one unit of work in the Executive's execution plan.

Immutable, like every value object in the Agent Framework: a task's
status/assigned_agent "change" by replacing the task with an updated copy
(with_status()/with_assigned_agent()), never by mutating it in place, so a
Task handed to a hook, event, or another collaborator can never be changed
out from under it later.
"""

import dataclasses
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from app.services.ai.agents.types import Metadata


class TaskStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class Task:
    title: str
    execution_id: str
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_task_id: str | None = None
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    assigned_agent: str | None = None
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.dependencies, tuple):
            object.__setattr__(self, "dependencies", tuple(self.dependencies))
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def __hash__(self) -> int:
        # metadata is a MappingProxyType, which has no __hash__ of its own
        # - hash on task_id alone, guaranteed unique per task and itself
        # immutable, exactly like SharedExecutionContext hashes on
        # execution_id rather than its own metadata mapping.
        return hash(self.task_id)

    def with_status(self, status: TaskStatus) -> "Task":
        return dataclasses.replace(self, status=status)

    def with_assigned_agent(self, agent_name: str) -> "Task":
        return dataclasses.replace(self, assigned_agent=agent_name, status=TaskStatus.ASSIGNED)
