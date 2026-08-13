"""ToolContext - who/what/why behind one tool invocation.

Composes SharedExecutionContext (app.services.ai.shared.execution_context)
rather than redefining execution identity itself: `shared` is the one
place execution_id/request_id/correlation_id/.../metadata live. Everything
declared directly on this class is genuinely tool-specific (which tool,
which agent invoked it, how deep in a delegation/execution chain, the
actual parameters to run it with).

cancellation_token reuses app.services.ai.runtime.cancellation.CancellationToken
directly rather than a parallel tools-specific token type - the same
cooperative-cancellation mechanism applies unchanged here.

__init__ is written by hand (not dataclass-generated) so every field
SharedExecutionContext already covers can still be passed as a flat
keyword argument directly to ToolContext(...), exactly like RuntimeContext/
AgentContext/the kernel's ExecutionContext.
"""

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from app.services.ai.runtime.cancellation import CancellationToken
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.tools.shared.types import Metadata


@dataclass(frozen=True, init=False)
class ToolContext:
    shared: SharedExecutionContext
    tool_id: str
    agent_id: str | None = None
    workflow_id: str | None = None
    execution_depth: int = 0
    parameters: Metadata = field(default_factory=lambda: MappingProxyType({}))
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))
    cancellation_token: CancellationToken | None = None

    def __init__(
        self,
        tool_id: str,
        shared: SharedExecutionContext | None = None,
        *,
        agent_id: str | None = None,
        workflow_id: str | None = None,
        execution_depth: int = 0,
        parameters: Metadata | None = None,
        metadata: Metadata | None = None,
        cancellation_token: CancellationToken | None = None,
        # backward-compatible flat kwargs, forwarded into a freshly built
        # `shared` when `shared` itself isn't given explicitly.
        execution_id: str | None = None,
        request_id: str | None = None,
        session_id: str | None = None,
        organization_id: int | None = None,
        user_id: int | None = None,
        conversation_id: int | None = None,
        shared_metadata: Metadata | None = None,
    ) -> None:
        if shared is None:
            shared_kwargs = {
                "execution_id": execution_id,
                "request_id": request_id,
                "session_id": session_id,
                "organization_id": organization_id,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "metadata": shared_metadata,
            }
            shared = SharedExecutionContext(**{k: v for k, v in shared_kwargs.items() if v is not None})
        object.__setattr__(self, "shared", shared)
        object.__setattr__(self, "tool_id", tool_id)
        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(self, "workflow_id", workflow_id)
        object.__setattr__(self, "execution_depth", execution_depth)
        object.__setattr__(self, "parameters", MappingProxyType(dict(parameters) if parameters else {}))
        object.__setattr__(self, "metadata", MappingProxyType(dict(metadata) if metadata else {}))
        object.__setattr__(self, "cancellation_token", cancellation_token)

    @property
    def execution_id(self) -> str:
        return self.shared.execution_id

    @property
    def request_id(self) -> str:
        return self.shared.request_id

    @property
    def parent_execution_id(self) -> str | None:
        return self.shared.parent_execution_id

    @property
    def correlation_id(self) -> str:
        return self.shared.correlation_id

    @property
    def causation_id(self) -> str | None:
        return self.shared.causation_id

    @property
    def organization_id(self) -> int | None:
        return self.shared.organization_id

    @property
    def user_id(self) -> int | None:
        return self.shared.user_id

    @property
    def session_id(self) -> str | None:
        return self.shared.session_id

    @property
    def conversation_id(self) -> int | None:
        return self.shared.conversation_id

    @property
    def created_at(self) -> datetime:
        return self.shared.created_at
