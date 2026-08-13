"""SpecialistTask - reusable, immutable task models every specialist
(Research today; Finance/Trading/Vision/... future) plans and executes
against. task_type is a closed taxonomy today with an explicit UNKNOWN
member for tasks that don't fit yet - new specialist domains are expected
to reuse these categories rather than each inventing their own.
"""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from app.services.ai.agents.types import Metadata


class SpecialistTaskType(StrEnum):
    RESEARCH = "research"
    ANALYSIS = "analysis"
    SUMMARIZATION = "summarization"
    COMPARISON = "comparison"
    VERIFICATION = "verification"
    INVESTIGATION = "investigation"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SpecialistTask:
    task_type: SpecialistTaskType
    title: str
    description: str = ""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def __hash__(self) -> int:
        # metadata is a MappingProxyType, unhashable - hash on task_id
        # alone, unique per task and itself immutable (same pattern as
        # app.services.ai.agents.executive.task.Task).
        return hash(self.task_id)
