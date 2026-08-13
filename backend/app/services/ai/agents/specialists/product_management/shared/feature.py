"""FeatureInitiative - a discrete unit of product work under consideration
or in flight (Architecture §7). Belongs to a Product, is grounded by
Discovery Findings, and is sequenced onto a Roadmap Item once prioritized
- those relationships are expressed by reference (a name/id), never by
nesting another domain object inside this one, so that each entity
remains an independent, individually-retrievable memory (Architecture
§7's own "realized as one or more categorized memories" principle).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_FEATURE


class FeatureStage(StrEnum):
    DISCOVERY = "discovery"
    DELIVERY = "delivery"
    SHIPPED = "shipped"
    SUNSET = "sunset"


@dataclass(frozen=True)
class FeatureInitiative:
    title: str
    problem_addressed: str = ""
    stage: FeatureStage = FeatureStage.DISCOVERY
    linked_evidence_ids: tuple[int, ...] = field(default_factory=tuple)
    priority_score: float | None = None
    product_name: str = ""
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_FEATURE

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("FeatureInitiative.title is required")
        if not isinstance(self.linked_evidence_ids, tuple):
            object.__setattr__(self, "linked_evidence_ids", tuple(self.linked_evidence_ids))
        if self.priority_score is not None and self.priority_score < 0:
            raise ValueError(f"FeatureInitiative.priority_score must be non-negative, got {self.priority_score}")

    def to_memory_content(self) -> str:
        parts = [f"Feature/Initiative: {self.title}."]
        if self.product_name:
            parts.append(f"Product: {self.product_name}.")
        if self.problem_addressed:
            parts.append(f"Problem addressed: {self.problem_addressed}.")
        parts.append(f"Stage: {self.stage.value}.")
        if self.priority_score is not None:
            parts.append(f"Priority score: {self.priority_score:g}.")
        if self.linked_evidence_ids:
            ids = ", ".join(str(i) for i in self.linked_evidence_ids)
            parts.append(f"Linked evidence: {ids}.")
        return " ".join(parts)
