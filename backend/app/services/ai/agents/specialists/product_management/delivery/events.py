"""DeliveryEvent - built on GenericEvent/EventPublisher, mirroring
DiscoveryEvent's/DecisionEvent's own precedent exactly (Milestones 3-4).
Event categories realize CP-02 Architecture §15: request lifecycle,
context-gathering, one family per operation, and a distinct
confidence-scored event for this milestone's own approved enhancement.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.services.ai.shared.events import EventPublisher, GenericEvent, hash_event


class DeliveryEventType(StrEnum):
    REQUEST_STARTED = "request_started"
    PRECEDENT_RETRIEVED = "precedent_retrieved"
    SPRINT_PLANNED = "sprint_planned"
    BACKLOG_REFINED = "backlog_refined"
    STORY_DECOMPOSED = "story_decomposed"
    EPIC_BROKEN_DOWN = "epic_broken_down"
    ACCEPTANCE_CRITERIA_GENERATED = "acceptance_criteria_generated"
    RISKS_DETECTED = "risks_detected"
    DEPENDENCIES_ANALYZED = "dependencies_analyzed"
    CONFIDENCE_SCORED = "confidence_scored"
    RECOMMENDATION_GENERATED = "recommendation_generated"
    ARTIFACT_STORED = "artifact_stored"
    FEATURE_STAGE_UPDATED = "feature_stage_updated"
    HANDOFF_SUPPORTED = "handoff_supported"
    DELIVERY_SUMMARIZED = "delivery_summarized"
    RETROSPECTIVE_SUPPORTED = "retrospective_supported"
    LAUNCH_READINESS_CHECKED = "launch_readiness_checked"
    RECALL_COMPLETED = "recall_completed"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_FAILED = "request_failed"


@dataclass(frozen=True, kw_only=True)
class DeliveryEvent(GenericEvent):
    event_type: DeliveryEventType
    agent_id: str

    __hash__ = hash_event


class DeliveryEventPublisher(EventPublisher[DeliveryEvent]):
    pass
