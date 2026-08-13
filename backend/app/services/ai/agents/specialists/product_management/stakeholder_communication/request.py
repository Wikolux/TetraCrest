"""StakeholderCommunicationRequest - what a caller asks the Stakeholder
Communication Specialist to do. Mirrors DiscoveryRequest's/DecisionRequest's/
DeliveryRequest's/StrategyRequest's own precedent exactly (Milestones 3-6).

Five operations, deliberately fewer than prior specialists despite this
milestone naming thirteen responsibilities: Architecture §11's own
"one architectural pattern, not one per channel" principle means twelve of
those thirteen (every drafting responsibility except stakeholder mapping
and decision explanations) are realized as `DRAFT_COMMUNICATION`,
parameterized by `audience`/`purpose` (see outputs.py) - not twelve
near-duplicate operations.
"""

from dataclasses import dataclass
from enum import StrEnum


class StakeholderCommunicationOperation(StrEnum):
    MAP_STAKEHOLDER = "map_stakeholder"
    DRAFT_COMMUNICATION = "draft_communication"
    EXPLAIN_DECISION = "explain_decision"
    SUMMARIZE_COMMUNICATIONS = "summarize_communications"
    RECALL = "recall"


@dataclass(frozen=True)
class StakeholderCommunicationRequest:
    operation: StakeholderCommunicationOperation
    text: str = ""
    title: str = ""
    subject: str = ""
    audience: str = ""
    purpose: str = ""
    stakeholder_name: str = ""
    role_or_interest: str = ""
    raci_role: str = ""
    communication_preference: str = ""
