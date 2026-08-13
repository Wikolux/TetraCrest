"""TaskResult - the outcome of running one Task.

Composes AgentExecutionResult when a task was genuinely delegated to
another BaseAgent (via an AgentExecutor - see dispatcher.py/executive_agent.py)
rather than duplicating its fields; `output` carries whatever a task the
Executive handled directly (memory retrieval, prompt building, ...)
produced (a ContextPackage, a PromptPackage, ...) when there was no
AgentExecutionResult to compose because no delegation occurred.
"""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.services.ai.agents.types import AgentExecutionResult, Metadata


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    success: bool
    output: Any = None
    agent_execution_result: AgentExecutionResult | None = None
    error: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
