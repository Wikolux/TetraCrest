"""Kernel execution context - now composes SharedExecutionContext
(app.services.ai.shared.execution_context) rather than redefining
execution identity itself.

This is the kernel's one sanctioned exception to "imports nothing from
elsewhere in app.services.ai" (see types.py): SharedExecutionContext is
the AI Operating System's single, unified execution identity, and every
subsystem - Kernel, Runtime, Agents - is meant to compose it rather than
keep three separate, overlapping definitions of the same concept. The
kernel still imports nothing else from elsewhere in app.services.ai - no
capabilities/, no providers/, no conversation/ - only this one shared
value-object module.

agent_id and capability remain kernel-specific (no equivalent field
exists on SharedExecutionContext) and are still plain strings, not
app.services.ai.capabilities.enums.Capability, for the same reason as
before: capability identity is passed through as data, never as a type
this layer has an opinion about. trace_id is gone - superseded by
SharedExecutionContext.correlation_id/causation_id, which cover the same
distributed-tracing need without a redundant kernel-only field.

__init__ is written by hand (not dataclass-generated) so every field
SharedExecutionContext already covers can still be passed as a flat
keyword argument directly to ExecutionContext(...), exactly as before
this milestone.
"""

from dataclasses import dataclass

from app.services.ai.kernel.types import Metadata
from app.services.ai.shared.execution_context import SharedExecutionContext


@dataclass(frozen=True, init=False)
class ExecutionContext:
    shared: SharedExecutionContext
    agent_id: str | None = None
    capability: str | None = None

    def __init__(
        self,
        shared: SharedExecutionContext | None = None,
        *,
        agent_id: str | None = None,
        capability: str | None = None,
        # backward-compatible flat kwargs, forwarded into a freshly built
        # `shared` when `shared` itself isn't given explicitly.
        request_id: str | None = None,
        organization_id: int | None = None,
        user_id: int | None = None,
        session_id: str | None = None,
        metadata: Metadata | None = None,
    ) -> None:
        if shared is None:
            shared_kwargs = {
                "request_id": request_id,
                "organization_id": organization_id,
                "user_id": user_id,
                "session_id": session_id,
                "metadata": metadata,
            }
            shared = SharedExecutionContext(**{k: v for k, v in shared_kwargs.items() if v is not None})
        object.__setattr__(self, "shared", shared)
        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(self, "capability", capability)

    @property
    def request_id(self) -> str:
        return self.shared.request_id

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
    def metadata(self) -> Metadata:
        return self.shared.metadata

    @property
    def execution_id(self) -> str:
        return self.shared.execution_id

    @property
    def parent_execution_id(self) -> str | None:
        return self.shared.parent_execution_id

    @property
    def correlation_id(self) -> str:
        return self.shared.correlation_id

    @property
    def causation_id(self) -> str | None:
        return self.shared.causation_id
