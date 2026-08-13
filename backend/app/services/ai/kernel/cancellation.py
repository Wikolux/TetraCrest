from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from app.services.ai.kernel.types import Metadata


class CancellationReason(StrEnum):
    """Why an execution was, or should be, cancelled."""

    USER_REQUESTED = "user_requested"
    TIMEOUT = "timeout"
    SUPERSEDED = "superseded"
    SYSTEM_SHUTDOWN = "system_shutdown"
    POLICY_VIOLATION = "policy_violation"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CancellationPolicy:
    """Declares how cancellation should behave for an execution - not an
    implementation. KernelRuntime does not implement cancellation yet;
    this is only the contract a future implementation will read.

    grace_period_ms is a concept (how long a cancelled execution is given
    to wind down) rather than a real timer - no scheduler/timeout
    mechanism exists in the kernel yet.
    """

    allow_cancellation: bool = True
    grace_period_ms: int | None = None
    propagate_to_children: bool = True


@dataclass(frozen=True)
class ExecutionCancellation:
    """A record that an execution was, or is being, cancelled.

    A value object describing a cancellation event, not a cancellation
    mechanism - nothing here performs the cancellation. request_id
    references the ExecutionContext.request_id of the execution being
    cancelled, by id rather than by holding a live context/request
    object, so a cancellation can be described even by something that
    only knows the id (e.g. an external cancellation API call).
    """

    request_id: str
    reason: CancellationReason
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
