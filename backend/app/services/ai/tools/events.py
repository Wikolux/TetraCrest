"""ToolEvent - identical in philosophy to Runtime/Agent/Executive events:
one typed event shape with an event-type discriminator, plus a publisher
that stores subscribers and dispatches to them synchronously. No event
bus, no external broker.

Every event carries execution_id, correlation_id, tool_id, and agent_id -
required identity fields, not optional, since every ToolEvent is always
emitted from within a real ToolExecutor.execute() call that always has a
full ToolContext and a resolved tool.

Built on GenericEvent/EventPublisher (app.services.ai.shared.events) rather
than hand-rolling the same shape/dispatch logic.
"""

from dataclasses import dataclass

from app.services.ai.shared.events import EventPublisher, GenericEvent, hash_event
from app.services.ai.tools.enums import ToolEventType


@dataclass(frozen=True, kw_only=True)
class ToolEvent(GenericEvent):
    event_type: ToolEventType
    tool_id: str
    agent_id: str | None = None

    __hash__ = hash_event


class ToolEventPublisher(EventPublisher[ToolEvent]):
    pass
