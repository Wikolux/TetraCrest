"""ResearchEvent - identical in philosophy to every other event type in
this platform (Runtime/Agent/Executive/Tool events): one typed event
shape with an event-type discriminator, plus a publisher that stores
subscribers and dispatches to them synchronously. No event bus, no
external broker.

Every event carries execution_id, correlation_id, agent_id, and
timestamp - required, not optional, since every ResearchEvent is always
emitted from within a real research() call that always has a full
SpecialistContext.

Built on GenericEvent/EventPublisher (app.services.ai.shared.events) rather
than hand-rolling the same shape/dispatch logic. ResearchEvent is currently
the only concrete "SpecialistEvent" in the platform - there is no separate,
specialist-generic event type today, since research/ is still the only
concrete specialist.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.services.ai.shared.events import EventPublisher, GenericEvent, hash_event


class ResearchEventType(StrEnum):
    RESEARCH_STARTED = "research_started"
    PLAN_CREATED = "plan_created"
    MEMORY_RETRIEVED = "memory_retrieved"
    TOOLS_COMPLETED = "tools_completed"
    SYNTHESIS_COMPLETED = "synthesis_completed"
    REPORT_GENERATED = "report_generated"
    RESEARCH_COMPLETED = "research_completed"
    RESEARCH_FAILED = "research_failed"


@dataclass(frozen=True, kw_only=True)
class ResearchEvent(GenericEvent):
    event_type: ResearchEventType
    agent_id: str

    __hash__ = hash_event


class ResearchEventPublisher(EventPublisher[ResearchEvent]):
    pass
