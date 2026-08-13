"""RoadmapItem - a sequenced commitment or intention on a product's
roadmap (Architecture §7). Carries its horizon and its dependency
relationships to other roadmap items, potentially across Products - the
cross-product edge Portfolio Intelligence's own reasoning (Architecture
§12) operates over once it matures beyond v1/v2 scope.

Roadmap state is append-only in the same sense every other CP-02 memory
category is (Architecture §6, corrected citation per ARR §6 and
Implementation_Plan §7): a "revision" to a roadmap is a new
RoadmapItem-shaped memory entry, referencing the item it supersedes,
never an edit of a prior entry in place - mirroring CP-01's own
GoalProgressUpdate precedent (CP-01 Implementation.md §5).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_ROADMAP


class RoadmapHorizon(StrEnum):
    NOW = "now"
    NEXT = "next"
    LATER = "later"


class RoadmapItemStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class RoadmapItem:
    title: str
    horizon: RoadmapHorizon = RoadmapHorizon.LATER
    status: RoadmapItemStatus = RoadmapItemStatus.PLANNED
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    product_name: str = ""
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_ROADMAP

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("RoadmapItem.title is required")
        if not isinstance(self.depends_on, tuple):
            object.__setattr__(self, "depends_on", tuple(self.depends_on))

    def to_memory_content(self) -> str:
        parts = [f"Roadmap item: {self.title}."]
        if self.product_name:
            parts.append(f"Product: {self.product_name}.")
        parts.append(f"Horizon: {self.horizon.value}. Status: {self.status.value}.")
        if self.depends_on:
            parts.append("Depends on: " + "; ".join(self.depends_on) + ".")
        return " ".join(parts)
