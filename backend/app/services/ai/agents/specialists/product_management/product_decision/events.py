"""DecisionEvent - built on GenericEvent/EventPublisher, mirroring
DiscoveryEvent's own precedent (Milestone 3) exactly. This milestone's own
task explicitly names six lifecycle events - REQUEST_STARTED,
FRAMEWORK_SELECTED, DECISION_GENERATED, DECISION_STORED, REQUEST_COMPLETED,
REQUEST_FAILED - all present below, plus the same category of
operation-specific and context-gathering events Discovery's own event set
already establishes as this platform's convention (Architecture §15).
"""

from dataclasses import dataclass
from enum import StrEnum

from app.services.ai.shared.events import EventPublisher, GenericEvent, hash_event


class DecisionEventType(StrEnum):
    REQUEST_STARTED = "request_started"
    PRECEDENT_RETRIEVED = "precedent_retrieved"
    FRAMEWORK_SELECTED = "framework_selected"
    PRIORITIZATION_COMPLETED = "prioritization_completed"
    TRADEOFFS_ANALYZED = "tradeoffs_analyzed"
    OPTIONS_COMPARED = "options_compared"
    RISKS_IDENTIFIED = "risks_identified"
    ASSUMPTIONS_VALIDATED = "assumptions_validated"
    CONFIDENCE_ASSESSED = "confidence_assessed"
    DECISION_GENERATED = "decision_generated"
    DECISION_STORED = "decision_stored"
    CRAFT_RECORD_STORED = "craft_record_stored"
    DECISION_SUMMARIZED = "decision_summarized"
    HISTORY_RETRIEVED = "history_retrieved"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_FAILED = "request_failed"


@dataclass(frozen=True, kw_only=True)
class DecisionEvent(GenericEvent):
    event_type: DecisionEventType
    agent_id: str

    __hash__ = hash_event


class DecisionEventPublisher(EventPublisher[DecisionEvent]):
    pass
