"""ToolResult - the outcome of one tool invocation.

Composes ExecutionMetrics (app.services.ai.kernel.metrics) rather than
inventing a parallel metrics type - the same shape RuntimeResponse/
AgentExecutionResult already use, so metrics stay consistent across the
whole platform.

execution_id/parent_execution_id/correlation_id/causation_id are copied
directly from the ToolContext.shared that produced this result (via
SharedExecutionContext.identity_fields(), never derived from events) by
ToolExecutor - the same identity-propagation pattern RuntimeResponse and
AgentExecutionResult follow. Defaults auto-generate a fresh uuid4 each
purely so a ToolResult remains constructible standalone in tests; real
executions always get real ones from ToolExecutor.
"""

import uuid
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.services.ai.kernel.metrics import ExecutionMetrics
from app.services.ai.tools.shared.types import Metadata


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: Any = None
    structured_output: Metadata | None = None
    artifacts: tuple[str, ...] = field(default_factory=tuple)
    metrics: ExecutionMetrics | None = None
    execution_time_ms: float = 0.0
    error: str | None = None
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_execution_id: str | None = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.artifacts, tuple):
            object.__setattr__(self, "artifacts", tuple(self.artifacts))
        if self.structured_output is not None and not isinstance(self.structured_output, MappingProxyType):
            object.__setattr__(self, "structured_output", MappingProxyType(dict(self.structured_output)))
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
