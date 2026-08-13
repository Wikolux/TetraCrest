"""GenericEvent/EventPublisher - the canonical typed-event value object plus
synchronous pub/sub for the whole AI Operating System, generalized after the
identical shape (one frozen dataclass with an event_type discriminator,
execution_id, correlation_id, timestamp, and a data mapping, plus a
publisher storing subscribers and dispatching synchronously) had already
been hand-copied across Runtime, Agent, Executive, Tool, and Research
events before Vision needed it a sixth time.

RuntimeEvent, AgentEvent, ExecutiveEvent, ToolEvent, ResearchEvent, and
VisionEvent all subclass GenericEvent - each keeps its own distinct,
isinstance-checkable type and adds only what's genuinely its own (ToolEvent
adds tool_id, AgentEvent makes execution_id optional, ...), while sharing
100% of the field/dispatch/hashing implementation.

kw_only=True is deliberate: every event across the platform is already
constructed with keyword arguments only (never positionally), and kw_only
is what lets a subclass add a *required* field (e.g. ToolEvent.tool_id)
after this base's already-defaulted fields (timestamp, data) without
violating dataclass field-ordering rules.

correlation_id defaults to execution_id when not given - the same
convention SharedExecutionContext uses (a root execution is the start of
its own correlation chain) - so event types that never explicitly tracked
a correlation_id before (RuntimeEvent, AgentEvent) gain one for free rather
than being forced to fabricate one at every call site.
"""

import time
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Generic, TypeVar

from app.services.ai.shared.execution_types import Metadata


def hash_event(event: "GenericEvent") -> int:
    """The one hashing strategy every event type in the platform uses.

    A frozen dataclass's auto-generated __hash__ hashes every field,
    including `data` - a MappingProxyType, which is unhashable (it wraps a
    dict). Hashing on (execution_id, event_type, timestamp) instead - never
    on `data` - sidesteps that while still being effectively unique per
    emitted event.

    Every GenericEvent subclass that is itself re-decorated with
    `@dataclass` (any subclass narrowing event_type's type, or adding a
    field) must explicitly restate `__hash__ = hash_event` in its own
    class body: `@dataclass(frozen=True)` regenerates a fresh, broken
    auto-hash for any class where `__hash__` isn't already present in that
    exact class's own namespace, so it does not transfer implicitly through
    ordinary inheritance the way a plain method would.
    """
    return hash((event.execution_id, event.event_type, event.timestamp))


@dataclass(frozen=True, kw_only=True)
class GenericEvent:
    event_type: Any
    execution_id: str
    correlation_id: str | None = None
    timestamp: float = field(default_factory=time.time)
    data: Metadata = field(default_factory=lambda: MappingProxyType({}))

    __hash__ = hash_event

    def __post_init__(self) -> None:
        if not isinstance(self.data, MappingProxyType):
            object.__setattr__(self, "data", MappingProxyType(dict(self.data)))
        if self.correlation_id is None:
            object.__setattr__(self, "correlation_id", self.execution_id)


TEvent = TypeVar("TEvent")
EventSubscriber = Callable[[TEvent], None]


class EventPublisher(Generic[TEvent]):
    """Stores subscribers and dispatches events to them synchronously, in
    subscription order, on the caller's own thread. No event bus, no
    external broker."""

    def __init__(self) -> None:
        self._subscribers: list[EventSubscriber] = []

    def subscribe(self, callback: EventSubscriber) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback: EventSubscriber) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def publish(self, event: TEvent) -> None:
        for subscriber in self._subscribers:
            subscriber(event)

    def subscriber_count(self) -> int:
        return len(self._subscribers)
