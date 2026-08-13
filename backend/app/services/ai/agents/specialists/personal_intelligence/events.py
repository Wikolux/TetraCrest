"""PersonalIntelligenceEvent - identical in philosophy to every other
event type in this platform: one typed event shape with an event-type
discriminator, plus a publisher that stores subscribers and dispatches
to them synchronously. No event bus, no external broker.

Built on GenericEvent/EventPublisher (app.services.ai.shared.events)
rather than hand-rolling the shape/dispatch logic - the same base every
event type in the platform has used since the M19 completion pass. Not a
new event mechanism - "No duplicate events" (this milestone's own
Architecture Rules) is honored by extending the existing generic exactly
like ResearchEvent/ExecutiveEvent/ToolEvent/VisionEvent already do.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.services.ai.shared.events import EventPublisher, GenericEvent, hash_event


class PersonalIntelligenceEventType(StrEnum):
    REQUEST_STARTED = "request_started"
    CONTEXT_RETRIEVED = "context_retrieved"
    IDENTITY_REMEMBERED = "identity_remembered"
    GOAL_REMEMBERED = "goal_remembered"
    GOAL_PROGRESS_UPDATED = "goal_progress_updated"
    PROJECT_REMEMBERED = "project_remembered"
    REFLECTION_REMEMBERED = "reflection_remembered"
    PREFERENCE_REMEMBERED = "preference_remembered"
    RECALL_COMPLETED = "recall_completed"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_FAILED = "request_failed"


@dataclass(frozen=True, kw_only=True)
class PersonalIntelligenceEvent(GenericEvent):
    event_type: PersonalIntelligenceEventType
    agent_id: str

    __hash__ = hash_event


class PersonalIntelligenceEventPublisher(EventPublisher[PersonalIntelligenceEvent]):
    pass
