from dataclasses import dataclass, field
from types import MappingProxyType

from app.services.ai.kernel.context import ExecutionContext
from app.services.ai.kernel.state import ExecutionState
from app.services.ai.kernel.types import Metadata, Payload


@dataclass(frozen=True)
class ExecutionRequest:
    """One request into the kernel.

    payload is deliberately typed as Payload (an alias for Any): the
    kernel must never know or assume anything about a PromptPackage, an
    image, an audio blob, or any other capability-specific shape - it
    only ever carries the payload through. capability is a plain string
    naming which capability this request is for (see ExecutionContext for
    why it isn't an enum from elsewhere in app.services.ai).

    options is a read-only mapping (like ExecutionContext.metadata), for
    execution-specific settings that aren't part of the payload itself
    (e.g. a future timeout or temperature override) without the kernel
    needing to know what any particular option means.
    """

    capability: str
    payload: Payload
    context: ExecutionContext
    options: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.options, MappingProxyType):
            object.__setattr__(self, "options", MappingProxyType(dict(self.options)))


@dataclass(frozen=True)
class ExecutionResponse:
    """One response out of the kernel.

    payload is Payload (Any) for the same reason ExecutionRequest.payload
    is: the kernel never interprets it, only carries it. usage and
    metadata are read-only mappings, coerced in __post_init__ exactly
    like ExecutionContext.metadata - usage stays a generic mapping rather
    than a capability-specific type (e.g. TokenUsage) so the kernel never
    needs to import anything from elsewhere in app.services.ai.

    state is the lifecycle state (see state.py) this response represents.
    success is kept - it isn't being removed, since existing callers
    already depend on it and it remains the simplest possible check for
    "did this work" - but state carries more: a caller can now tell
    FAILED apart from CANCELLED, something `success=False` alone can't
    express. When state isn't given explicitly, it's derived from
    success (COMPLETED if True, FAILED if False) so every existing
    ExecutionResponse(success=...) call site keeps working unchanged
    while still getting a meaningful state.
    """

    success: bool
    payload: Payload = None
    provider: str | None = None
    latency_ms: float | None = None
    usage: Metadata | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))
    error: str | None = None
    state: ExecutionState | None = None

    def __post_init__(self) -> None:
        if self.usage is not None and not isinstance(self.usage, MappingProxyType):
            object.__setattr__(self, "usage", MappingProxyType(dict(self.usage)))
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if self.state is None:
            object.__setattr__(
                self, "state", ExecutionState.COMPLETED if self.success else ExecutionState.FAILED
            )
