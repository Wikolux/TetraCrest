"""SharedExecutionContext - the one execution identity shared by the
Kernel, Runtime, and Agent Framework.

Before this milestone, three subsystems each defined their own notion of
"who/what/why behind this execution" (kernel.context.ExecutionContext,
runtime.types.RuntimeContext, agents.context.AgentContext), describing the
same underlying concept from three different angles. This type is the
single place execution identity is defined; every subsystem now composes
it (holds one as a field) and adds only what's genuinely specific to that
layer, rather than redefining organization_id/session_id/request_id/
metadata three separate times.

This module depends on nothing except shared/execution_types.py (plain
type aliases) - the shared model must not depend on the Kernel, Runtime,
Agents, or anything provider/capability-specific, so every one of those
can depend on it without risking a cycle.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType

from app.services.ai.shared.execution_types import Metadata


@dataclass(frozen=True)
class SharedExecutionContext:
    """Immutable identity for one execution, anywhere in the AI Operating
    System.

    execution_id is this execution's own identity and never changes once
    set (frozen, like every field here). parent_execution_id links a
    nested execution (a sub-agent, a tool call, a runtime invocation
    triggered by an agent) back to whatever execution spawned it, forming
    an execution tree - see child(). correlation_id ties every execution
    in one causal chain together for observability/tracing; when not
    given explicitly it defaults to this context's own execution_id (a
    root execution is the start of its own correlation chain, the same
    convention distributed tracing systems use for a trace's root span).
    causation_id is optional and names whatever specific event/execution
    directly caused this one, distinct from correlation_id (the whole
    chain) and parent_execution_id (the execution tree specifically).

    Hashable despite holding a MappingProxyType field: __hash__ is based
    on execution_id alone (guaranteed unique per execution and itself
    immutable), since MappingProxyType has no __hash__ of its own and
    hashing the rest of a context's identity fields would be redundant -
    execution_id already uniquely identifies it.
    """

    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_execution_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    session_id: str | None = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: int | None = None
    user_id: int | None = None
    conversation_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if self.correlation_id is None:
            object.__setattr__(self, "correlation_id", self.execution_id)

    def __hash__(self) -> int:
        return hash(self.execution_id)

    def child(self, **overrides) -> "SharedExecutionContext":
        """Build a SharedExecutionContext for an execution nested under
        this one - Executive -> Agent -> Sub-Agent -> Tool -> Runtime all
        belonging to one execution tree.

        By default: a fresh execution_id/request_id, parent_execution_id
        and causation_id set to this context's own execution_id (this
        execution is both the parent and the direct cause of the child),
        and correlation_id/session_id/organization_id/user_id/
        conversation_id propagated unchanged - the whole chain shares one
        correlation_id unless a caller deliberately overrides it. Any
        field can be overridden via keyword argument.
        """
        defaults = dict(
            parent_execution_id=self.execution_id,
            correlation_id=self.correlation_id,
            causation_id=self.execution_id,
            session_id=self.session_id,
            organization_id=self.organization_id,
            user_id=self.user_id,
            conversation_id=self.conversation_id,
        )
        defaults.update(overrides)
        return SharedExecutionContext(**defaults)

    def identity_fields(self) -> dict[str, str | None]:
        """The four identity fields every execution artifact
        (RuntimeResponse, AgentExecutionResult, ExecutionMetrics, ...)
        copies onto itself, so an Executive never has to inspect events to
        answer "which execution produced this."

        The one place this mapping is defined - RuntimeExecutor and
        AgentExecutor both build their result objects with
        `**context.shared.identity_fields()` rather than each spelling out
        `execution_id=..., parent_execution_id=..., ...` independently.
        """
        return {
            "execution_id": self.execution_id,
            "parent_execution_id": self.parent_execution_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }
