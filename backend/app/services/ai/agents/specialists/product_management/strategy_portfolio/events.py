"""StrategyEvent - built on GenericEvent/EventPublisher, mirroring
DiscoveryEvent's/DecisionEvent's/DeliveryEvent's own precedent exactly
(Milestones 3-5). Architecture §15 explicitly names "roadmap-revised" and
"cross-product-conflict-surfaced" as this specialist's own event family.
CROSS_PRODUCT_CONFLICT_SURFACED is declared here for documentation
completeness (matching Architecture's own named category) but is never
emitted by any Milestone 6 operation - cross-product reasoning is a
defined, dormant extension in this milestone, not working functionality
(Architecture §12, Implementation_Plan.md Milestone 6).
"""

from dataclasses import dataclass
from enum import StrEnum

from app.services.ai.shared.events import EventPublisher, GenericEvent, hash_event


class StrategyEventType(StrEnum):
    REQUEST_STARTED = "request_started"
    PRECEDENT_RETRIEVED = "precedent_retrieved"
    ROADMAP_REVISED = "roadmap_revised"
    INITIATIVES_PRIORITIZED = "initiatives_prioritized"
    OPPORTUNITIES_COMPARED = "opportunities_compared"
    VISION_ALIGNMENT_ASSESSED = "vision_alignment_assessed"
    NORTH_STAR_STRUCTURED = "north_star_structured"
    OKRS_STRUCTURED = "okrs_structured"
    TRADEOFFS_ASSESSED = "tradeoffs_assessed"
    RECOMMENDATION_GENERATED = "recommendation_generated"
    PORTFOLIO_ASSESSED = "portfolio_assessed"
    # Reserved for the future v3 cross-product Portfolio Intelligence
    # maturity (Architecture §12) - never emitted in Milestone 6.
    CROSS_PRODUCT_CONFLICT_SURFACED = "cross_product_conflict_surfaced"
    STRATEGY_SUMMARIZED = "strategy_summarized"
    RECALL_COMPLETED = "recall_completed"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_FAILED = "request_failed"


@dataclass(frozen=True, kw_only=True)
class StrategyEvent(GenericEvent):
    event_type: StrategyEventType
    agent_id: str

    __hash__ = hash_event


class StrategyEventPublisher(EventPublisher[StrategyEvent]):
    pass
