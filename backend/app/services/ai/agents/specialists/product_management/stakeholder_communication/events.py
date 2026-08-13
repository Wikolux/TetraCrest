"""CommunicationEvent - built on GenericEvent/EventPublisher, mirroring
DiscoveryEvent's/DecisionEvent's/DeliveryEvent's/StrategyEvent's own
precedent exactly (Milestones 3-6). ARR §3 names this specialist's own
event family precisely: "Request lifecycle; update-drafted" -
`UPDATE_DRAFTED` below is that literal event, emitted for every
`DRAFT_COMMUNICATION` call regardless of audience/purpose (Architecture
§11's "not a different code path" applies to events too).
"""

from dataclasses import dataclass
from enum import StrEnum

from app.services.ai.shared.events import EventPublisher, GenericEvent, hash_event


class CommunicationEventType(StrEnum):
    REQUEST_STARTED = "request_started"
    PRECEDENT_RETRIEVED = "precedent_retrieved"
    STAKEHOLDER_MAPPED = "stakeholder_mapped"
    UPDATE_DRAFTED = "update_drafted"
    ARTIFACT_STORED = "artifact_stored"
    DECISION_EXPLAINED = "decision_explained"
    COMMUNICATIONS_SUMMARIZED = "communications_summarized"
    RECALL_COMPLETED = "recall_completed"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_FAILED = "request_failed"


@dataclass(frozen=True, kw_only=True)
class CommunicationEvent(GenericEvent):
    event_type: CommunicationEventType
    agent_id: str

    __hash__ = hash_event


class CommunicationEventPublisher(EventPublisher[CommunicationEvent]):
    pass
