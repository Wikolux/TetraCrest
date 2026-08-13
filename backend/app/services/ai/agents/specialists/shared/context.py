"""SpecialistContext - composes AgentContext (which itself already
composes SharedExecutionContext) plus the one thing every specialist
needs that AgentContext has no place for: the SpecialistRequest driving
this invocation.

Never duplicates execution identity - shared/execution_id/correlation_id/
etc. are all reached via delegating properties into agent_context,
exactly like app.services.ai.agents.executive.context.ExecutiveContext.
"""

from dataclasses import dataclass, field
from types import MappingProxyType

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.shared.request import SpecialistRequest
from app.services.ai.agents.types import Metadata
from app.services.ai.shared.execution_context import SharedExecutionContext


@dataclass(frozen=True)
class SpecialistContext:
    agent_context: AgentContext
    request: SpecialistRequest | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def shared(self) -> SharedExecutionContext:
        return self.agent_context.shared

    @property
    def execution_id(self) -> str:
        return self.agent_context.execution_id

    @property
    def correlation_id(self) -> str:
        return self.agent_context.correlation_id

    @property
    def causation_id(self) -> str | None:
        return self.agent_context.causation_id

    @property
    def parent_execution_id(self) -> str | None:
        return self.agent_context.parent_execution_id

    @property
    def organization_id(self) -> int | None:
        return self.agent_context.organization_id

    @property
    def conversation_id(self) -> int | None:
        return self.agent_context.conversation_id

    @property
    def agent_id(self) -> str | None:
        return self.agent_context.agent_id
