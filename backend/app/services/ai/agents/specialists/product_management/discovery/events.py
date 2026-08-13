"""DiscoveryEvent - built on GenericEvent/EventPublisher
(app.services.ai.shared.events), the same base every event type on the
platform has used since the M19 completion pass. Not a new event
mechanism - CP-02 Architecture §15 event categories, realized:

1. Request lifecycle: REQUEST_STARTED/REQUEST_COMPLETED/REQUEST_FAILED.
2. Context-gathering milestones: PRECEDENT_RETRIEVED (a single retrieval
   through ProfessionalMemoryService surfaces both CP-02's own product_*
   memories and, when semantically relevant, CP-01-authored personal_*
   memories - both are read through the same organization-scoped,
   semantic MemoryRetrievalPipeline query, per Architecture §5/§19, so
   there is no separate "CP-01 event" to distinguish at this layer).
3. Capability-specific milestones: one per Discovery operation.
4. Delegation events: RESEARCH_QUESTION_FRAMED (distinguished from a
   locally-completed capability, per Architecture §15 point 4) and
   RESEARCH_FINDING_RECORDED.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.services.ai.shared.events import EventPublisher, GenericEvent, hash_event


class DiscoveryEventType(StrEnum):
    REQUEST_STARTED = "request_started"
    PRECEDENT_RETRIEVED = "precedent_retrieved"
    PROBLEM_STATEMENT_DRAFTED = "problem_statement_drafted"
    JTBD_FRAMED = "jtbd_framed"
    INTERVIEW_SYNTHESIZED = "interview_synthesized"
    OPPORTUNITY_ASSESSED = "opportunity_assessed"
    PERSONA_FRAMED = "persona_framed"
    HYPOTHESIS_STATUS_CHANGED = "hypothesis_status_changed"
    FINDING_RECORDED = "finding_recorded"
    RECOMMENDATION_GENERATED = "recommendation_generated"
    DISCOVERY_REPORT_GENERATED = "discovery_report_generated"
    SUMMARY_GENERATED = "summary_generated"
    RESEARCH_QUESTION_FRAMED = "research_question_framed"
    RESEARCH_FINDING_RECORDED = "research_finding_recorded"
    RECALL_COMPLETED = "recall_completed"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_FAILED = "request_failed"


@dataclass(frozen=True, kw_only=True)
class DiscoveryEvent(GenericEvent):
    event_type: DiscoveryEventType
    agent_id: str

    __hash__ = hash_event


class DiscoveryEventPublisher(EventPublisher[DiscoveryEvent]):
    pass
