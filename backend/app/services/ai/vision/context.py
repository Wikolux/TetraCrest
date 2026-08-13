"""VisionContext - who/what/why behind one vision execution. Composes
SharedExecutionContext (app.services.ai.shared.execution_context) rather
than redefining execution identity - the same composition pattern as
RuntimeContext/ToolContext/AgentContext/SpecialistContext.

__init__ is written by hand so every field SharedExecutionContext already
covers can still be passed as a flat keyword argument directly to
VisionContext(...), exactly like every other composed context in this
platform.
"""

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.vision.capabilities.enums import VisionCapabilityCategory
from app.services.ai.vision.shared.types import Metadata


@dataclass(frozen=True, init=False)
class VisionContext:
    shared: SharedExecutionContext
    agent_id: str | None = None
    capability_category: VisionCapabilityCategory | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __init__(
        self,
        shared: SharedExecutionContext | None = None,
        *,
        agent_id: str | None = None,
        capability_category: VisionCapabilityCategory | None = None,
        metadata: Metadata | None = None,
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
        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(self, "capability_category", capability_category)
        object.__setattr__(self, "metadata", MappingProxyType(dict(metadata) if metadata else {}))

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
