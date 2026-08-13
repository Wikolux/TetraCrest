"""Stakeholder Communication Specialist structured outputs (Milestone 7) -
mirrors Discovery's/Product Decision's/Delivery's/Strategy's own
outputs.py precedent exactly (Milestones 3-6): every type here is a
synthesis/response-shaping structure, never a memory type of its own.
`Stakeholder` is Milestone 1's own type (shared/stakeholder.py), written
here via ProfessionalMemoryService, never redefined. `DeliveryArtifact` is
Milestone 5's own type (shared/delivery_artifact.py), reused with its new
`COMMUNICATION_DRAFT` member for this specialist's own durable writes,
also never redefined.

Architecture §11 is explicit and structural, not just a style preference:
"An executive summary versus an engineering-facing status note is a
template/format choice at prompt-assembly time, not a different code
path... the identical reasoning CP-01 Architecture §14 gives for why
Communication Intelligence never became five channel-specific
components." Every one of this milestone's twelve named communication
"kinds" (executive summaries, stakeholder updates, product status
reports, roadmap communication, sprint communication, leadership
briefings, product announcements, customer communication, engineering
handoff summaries, meeting follow-up summaries, product vision
communication, portfolio communication) is therefore realized as the
*same* `CommunicationDraft` type, parameterized by `audience` and
`purpose` - never as twelve near-identical dataclasses. Concretely: an
"ExecutiveBrief" is `CommunicationDraft(purpose=EXECUTIVE_SUMMARY,
audience=EXECUTIVE, ...)`; a "CustomerCommunication" is the same type with
`purpose=CUSTOMER_COMMUNICATION, audience=CUSTOMER`; and so on for every
other named example this milestone's own task listed. `DecisionExplanation`
is kept as its own type only because it has a genuinely different input
shape (it always references one specific, named decision), not because
its audience-handling differs.

`CommunicationDraft` and `DecisionExplanation` both carry every field this
milestone's evidence discipline requires: audience, supporting evidence,
assumptions, confidence, and referenced memory IDs. Neither can be
constructed without referenced_memory_ids or an explicit evidence_gap -
"never invents facts" is a property of the type.
"""

from dataclasses import dataclass, field
from enum import StrEnum


def _as_tuple(value) -> tuple:
    return value if isinstance(value, tuple) else tuple(value)


class CommunicationAudience(StrEnum):
    EXECUTIVE = "executive"
    ENGINEERING = "engineering"
    CUSTOMER = "customer"
    LEADERSHIP = "leadership"
    GENERAL_STAKEHOLDER = "general_stakeholder"


class CommunicationPurpose(StrEnum):
    EXECUTIVE_SUMMARY = "executive_summary"
    STAKEHOLDER_UPDATE = "stakeholder_update"
    STATUS_REPORT = "status_report"
    ROADMAP_COMMUNICATION = "roadmap_communication"
    SPRINT_COMMUNICATION = "sprint_communication"
    LEADERSHIP_BRIEFING = "leadership_briefing"
    PRODUCT_ANNOUNCEMENT = "product_announcement"
    CUSTOMER_COMMUNICATION = "customer_communication"
    ENGINEERING_HANDOFF_SUMMARY = "engineering_handoff_summary"
    MEETING_FOLLOWUP = "meeting_followup"
    VISION_COMMUNICATION = "vision_communication"
    PORTFOLIO_COMMUNICATION = "portfolio_communication"


@dataclass(frozen=True)
class CommunicationDraft:
    audience: str
    purpose: str
    content: str
    supporting_evidence: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0
    referenced_memory_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_gap: str = ""

    def __post_init__(self) -> None:
        if not self.audience:
            raise ValueError("CommunicationDraft.audience is required - every draft must name its intended audience")
        if not self.purpose:
            raise ValueError("CommunicationDraft.purpose is required")
        if not self.content:
            raise ValueError("CommunicationDraft.content is required")
        object.__setattr__(self, "supporting_evidence", _as_tuple(self.supporting_evidence))
        object.__setattr__(self, "assumptions", _as_tuple(self.assumptions))
        if not self.assumptions:
            raise ValueError("CommunicationDraft.assumptions must not be empty - every assumption must be named")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("CommunicationDraft.confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "referenced_memory_ids", _as_tuple(self.referenced_memory_ids))
        if not self.referenced_memory_ids and not self.evidence_gap:
            raise ValueError(
                "CommunicationDraft must cite referenced_memory_ids or state an explicit evidence_gap - a "
                "draft may never imply facts not supported by evidence"
            )


@dataclass(frozen=True)
class DecisionExplanation:
    decision_title: str
    audience: str
    explanation: str
    supporting_evidence: tuple[str, ...] = field(default_factory=tuple)
    referenced_memory_ids: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0
    evidence_gap: str = ""

    def __post_init__(self) -> None:
        if not self.decision_title:
            raise ValueError("DecisionExplanation.decision_title is required")
        if not self.audience:
            raise ValueError("DecisionExplanation.audience is required")
        if not self.explanation:
            raise ValueError("DecisionExplanation.explanation is required")
        object.__setattr__(self, "supporting_evidence", _as_tuple(self.supporting_evidence))
        object.__setattr__(self, "referenced_memory_ids", _as_tuple(self.referenced_memory_ids))
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("DecisionExplanation.confidence must be between 0.0 and 1.0")
        if not self.referenced_memory_ids and not self.evidence_gap:
            raise ValueError(
                "DecisionExplanation must cite referenced_memory_ids or state an explicit evidence_gap - a "
                "decision explanation may never imply an outcome not supported by the actual Decision Record"
            )


@dataclass(frozen=True)
class StakeholderMappingResult:
    name: str
    raci_role: str = ""
    role_or_interest: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("StakeholderMappingResult.name is required")


@dataclass(frozen=True)
class CommunicationSummary:
    summary: str
    stakeholder_count: int = 0
    draft_count: int = 0

    def __post_init__(self) -> None:
        if not self.summary:
            raise ValueError("CommunicationSummary.summary is required")
