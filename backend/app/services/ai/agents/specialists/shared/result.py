"""SpecialistResult - the internal, per-step outcome within a specialist's
own workflow (one memory retrieval, one tool call, one synthesis step) -
distinct from SpecialistResponse, the single public result returned to
whoever invoked the specialist. Mirrors the same internal/public split
already established by RuntimeExecutionResult vs. RuntimeResponse, and by
app.services.ai.agents.executive.task_result.TaskResult vs. the
Executive's own final RuntimeResponse.
"""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.services.ai.agents.types import Metadata


@dataclass(frozen=True)
class SpecialistResult:
    step: str
    success: bool
    output: Any = None
    error: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
