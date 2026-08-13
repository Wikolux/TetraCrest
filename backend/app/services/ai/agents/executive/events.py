"""ExecutiveEvent - identical in philosophy to Runtime/Agent events: one
typed event shape with an event-type discriminator, plus a publisher that
stores subscribers and dispatches to them synchronously. No event bus, no
external broker.

Every event carries both execution_id and correlation_id directly (from
SharedExecutionContext, via ExecutiveContext) - required, not optional
like AgentEvent.execution_id, since every ExecutiveEvent is always emitted
from within a real request cycle that always has a context.

Built on GenericEvent/EventPublisher (app.services.ai.shared.events) rather
than hand-rolling the same shape/dispatch logic.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.services.ai.shared.events import EventPublisher, GenericEvent, hash_event


class ExecutiveEventType(StrEnum):
    PLAN_CREATED = "plan_created"
    TASK_CREATED = "task_created"
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    DELEGATION_STARTED = "delegation_started"
    DELEGATION_COMPLETED = "delegation_completed"
    RESPONSE_GENERATED = "response_generated"


@dataclass(frozen=True, kw_only=True)
class ExecutiveEvent(GenericEvent):
    event_type: ExecutiveEventType

    __hash__ = hash_event


class ExecutiveEventPublisher(EventPublisher[ExecutiveEvent]):
    pass
