"""InsightEvent - identical in philosophy to every other event type in
this platform: one typed event shape with an event-type discriminator,
plus a publisher that stores subscribers and dispatches to them
synchronously. Built on GenericEvent/EventPublisher
(app.services.ai.shared.events), not a new event mechanism - the same
base PersonalIntelligenceEvent/ResearchEvent/ExecutiveEvent already use.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.services.ai.shared.events import EventPublisher, GenericEvent, hash_event


class InsightEventType(StrEnum):
    REQUEST_STARTED = "request_started"
    CORPUS_GATHERED = "corpus_gathered"
    PATTERNS_DETECTED = "patterns_detected"
    HABITS_IDENTIFIED = "habits_identified"
    CONTRADICTIONS_DETECTED = "contradictions_detected"
    ALIGNMENT_MEASURED = "alignment_measured"
    PERIODIC_REFLECTION_GENERATED = "periodic_reflection_generated"
    RECOMMENDATIONS_GENERATED = "recommendations_generated"
    PROFILE_UPDATED = "profile_updated"
    RECALL_COMPLETED = "recall_completed"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_FAILED = "request_failed"


@dataclass(frozen=True, kw_only=True)
class InsightEvent(GenericEvent):
    event_type: InsightEventType
    agent_id: str

    __hash__ = hash_event


class InsightEventPublisher(EventPublisher[InsightEvent]):
    pass
