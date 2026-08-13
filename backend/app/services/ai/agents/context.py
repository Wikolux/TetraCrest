"""AgentContext - who/what/why behind one agent execution.

Composes SharedExecutionContext (app.services.ai.shared.execution_context)
rather than redefining execution identity itself: `shared` is the one
place execution_id/request_id/session_id/organization_id/user_id/
conversation_id/metadata live now. Everything declared directly on this
class is genuinely agent-specific (which agent, which workflow, how deep
in a delegation chain) - runtime concerns (provider, attempt, timeout)
belong on RuntimeContext, never here.

__init__ is written by hand (not dataclass-generated) so that every field
SharedExecutionContext already covers can still be passed as a flat
keyword argument directly to AgentContext(...), exactly as before this
milestone - existing callers that never knew about SharedExecutionContext
keep working unmodified. Passing `shared=` explicitly skips that
translation entirely for callers that want full control (e.g. an
orchestrator building a child context via SharedExecutionContext.child()).
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.shared.execution_metadata import ExecutionMetadata
from app.services.ai.shared.execution_types import Metadata


@dataclass(frozen=True, init=False)
class AgentContext:
    shared: SharedExecutionContext
    agent_id: str | None = None
    workflow_id: str | None = None
    parent_agent_id: str | None = None
    delegation_depth: int = 0
    agent_metadata: ExecutionMetadata = field(default_factory=ExecutionMetadata)

    def __init__(
        self,
        shared: SharedExecutionContext | None = None,
        *,
        agent_id: str | None = None,
        workflow_id: str | None = None,
        parent_agent_id: str | None = None,
        delegation_depth: int = 0,
        agent_metadata: ExecutionMetadata | None = None,
        # backward-compatible flat kwargs, forwarded into a freshly built
        # `shared` when `shared` itself isn't given explicitly.
        execution_id: str | None = None,
        request_id: str | None = None,
        session_id: str | None = None,
        organization_id: int | None = None,
        user_id: int | None = None,
        conversation_id: int | None = None,
        metadata: Metadata | None = None,
    ) -> None:
        if shared is None:
            shared_kwargs = {
                "execution_id": execution_id,
                "request_id": request_id,
                "session_id": session_id,
                "organization_id": organization_id,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "metadata": metadata,
            }
            shared = SharedExecutionContext(**{k: v for k, v in shared_kwargs.items() if v is not None})
        object.__setattr__(self, "shared", shared)
        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(self, "workflow_id", workflow_id)
        object.__setattr__(self, "parent_agent_id", parent_agent_id)
        object.__setattr__(self, "delegation_depth", delegation_depth)
        object.__setattr__(self, "agent_metadata", agent_metadata if agent_metadata is not None else ExecutionMetadata())

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
    def session_id(self) -> str | None:
        return self.shared.session_id

    @property
    def organization_id(self) -> int | None:
        return self.shared.organization_id

    @property
    def user_id(self) -> int | None:
        return self.shared.user_id

    @property
    def conversation_id(self) -> int | None:
        return self.shared.conversation_id

    @property
    def created_at(self) -> datetime:
        return self.shared.created_at

    @property
    def metadata(self) -> Metadata:
        return self.shared.metadata
