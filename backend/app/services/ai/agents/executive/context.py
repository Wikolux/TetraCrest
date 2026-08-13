"""ExecutiveContext - composes AgentContext (which itself already composes
SharedExecutionContext) plus Executive-specific information the base
AgentContext has no place for: the user's request text and any prior
conversation turns to feed into PromptBuilder.

Does not hold its own `shared` field - execution identity lives in
exactly one place (agent_context.shared), reached here via delegating
properties, exactly like every other composed context in this platform.
"""

from dataclasses import dataclass, field
from types import MappingProxyType

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.types import Metadata
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.prompt_builder.types import PromptMessage


@dataclass(frozen=True)
class ExecutiveContext:
    agent_context: AgentContext
    user_request: str = ""
    conversation_history: tuple[PromptMessage, ...] = field(default_factory=tuple)
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.conversation_history, tuple):
            object.__setattr__(self, "conversation_history", tuple(self.conversation_history))
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
    def organization_id(self) -> int | None:
        return self.agent_context.organization_id

    @property
    def conversation_id(self) -> int | None:
        return self.agent_context.conversation_id
