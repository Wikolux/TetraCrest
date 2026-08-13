"""Immutable kernel event types.

These describe things that happened during an execution - no event bus,
publisher, or subscriber mechanism exists here or anywhere in the kernel.
A future implementation would construct these and hand them to whatever
observability/eventing mechanism it introduces; this module only defines
their shape.

Every event now also carries execution_id (from
app.services.ai.shared.execution_context.SharedExecutionContext, via
ExecutionContext.execution_id) alongside its existing request_id -
distinct, not duplicate, identifiers: request_id has always identified
"which kernel request", execution_id identifies "which node in the
execution tree" (see SharedExecutionContext.child()) this event belongs
to. Optional and defaulted to None to preserve every existing call site -
nothing in the kernel constructs these in production yet, but tests do,
and none of them need to change.
"""

from dataclasses import dataclass, field
from types import MappingProxyType

from app.services.ai.kernel.cancellation import CancellationReason
from app.services.ai.kernel.state import ExecutionState
from app.services.ai.kernel.types import Metadata


def _freeze_metadata(instance) -> None:
    if not isinstance(instance.metadata, MappingProxyType):
        object.__setattr__(instance, "metadata", MappingProxyType(dict(instance.metadata)))


@dataclass(frozen=True)
class ExecutionStarted:
    """An execution began. capability is a plain string (see
    ExecutionContext for why the kernel never imports the Capability enum)."""

    request_id: str
    capability: str
    execution_id: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_metadata(self)


@dataclass(frozen=True)
class ExecutionCompleted:
    """An execution reached a terminal state."""

    request_id: str
    state: ExecutionState
    execution_id: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_metadata(self)


@dataclass(frozen=True)
class ExecutionFailed:
    """An execution failed. error is a plain description, not a
    provider-specific exception object - consistent with
    ExecutionResponse.error."""

    request_id: str
    error: str
    execution_id: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_metadata(self)


@dataclass(frozen=True)
class ExecutionCancelled:
    """An execution was cancelled."""

    request_id: str
    reason: CancellationReason
    execution_id: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_metadata(self)


@dataclass(frozen=True)
class ExecutionRetried:
    """An execution is being retried. attempt is the retry attempt number
    (1 for the first retry, not the first overall attempt)."""

    request_id: str
    attempt: int
    execution_id: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_metadata(self)


@dataclass(frozen=True)
class ProviderResolved:
    """A provider was resolved for an execution. provider is a plain
    string, consistent with ExecutionResponse.provider."""

    request_id: str
    provider: str
    execution_id: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_metadata(self)


@dataclass(frozen=True)
class CapabilityResolved:
    """A capability runtime was resolved for an execution."""

    request_id: str
    capability: str
    execution_id: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _freeze_metadata(self)


KernelEvent = (
    ExecutionStarted
    | ExecutionCompleted
    | ExecutionFailed
    | ExecutionCancelled
    | ExecutionRetried
    | ProviderResolved
    | CapabilityResolved
)
"""Type alias for "any kernel event" - useful for type-hinting a future
event consumer's signature (e.g. `def publish(event: KernelEvent)`)
without that consumer existing yet."""
