"""SpecialistResponse - the single public result a specialist returns for
one SpecialistRequest, generic across every specialist domain.

Composes ExecutionMetrics (app.services.ai.kernel.metrics) rather than a
new metrics type. success/error are not in the milestone's literal field
list but are added deliberately, matching the same success/error split
every other result type in this platform has (RuntimeResponse,
AgentExecutionResult, ToolResult) - state alone can't say *why* something
failed.

execution_id/parent_execution_id/correlation_id/causation_id are copied
directly from whatever SharedExecutionContext produced this response
(via identity_fields()), the same pattern as every other execution
artifact in the platform.
"""

import uuid
from dataclasses import dataclass, field
from types import MappingProxyType

from app.services.ai.agents.types import Metadata
from app.services.ai.kernel.metrics import ExecutionMetrics


@dataclass(frozen=True)
class SpecialistResponse:
    success: bool
    summary: str = ""
    findings: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0
    sources: tuple[str, ...] = field(default_factory=tuple)
    recommendations: tuple[str, ...] = field(default_factory=tuple)
    artifacts: tuple[str, ...] = field(default_factory=tuple)
    reasoning_summary: str = ""
    execution_metrics: ExecutionMetrics | None = None
    error: str | None = None
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_execution_id: str | None = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        for tuple_field in ("findings", "sources", "recommendations", "artifacts"):
            value = getattr(self, tuple_field)
            if not isinstance(value, tuple):
                object.__setattr__(self, tuple_field, tuple(value))
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
