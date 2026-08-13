"""Goal - a persistent, long-term goal the user is tracking.

GoalCategory is deliberately a small suggested vocabulary, not an
exhaustively closed one the way IdentityAttribute is - a goal's category
is descriptive, used for readability and light grouping in retrieved
context, never for structured filtering (the Memory Framework has none -
see Architecture.md §9), so nothing breaks if a caller passes a category
outside this list.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.services.ai.agents.specialists.personal_intelligence.shared.types import MEMORY_TYPE_GOAL


class GoalCategory(StrEnum):
    CAREER = "career"
    LEARNING = "learning"
    BUSINESS = "business"
    PERSONAL = "personal"
    RELATIONSHIP = "relationship"
    FINANCIAL = "financial"


class GoalStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass(frozen=True)
class Goal:
    title: str
    description: str = ""
    category: str = GoalCategory.PERSONAL
    priority: int = 0
    progress: float = 0.0
    status: GoalStatus = GoalStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None

    memory_type = MEMORY_TYPE_GOAL

    def __post_init__(self) -> None:
        if not 0.0 <= self.progress <= 100.0:
            raise ValueError(f"Goal.progress must be between 0 and 100, got {self.progress}")

    def to_memory_content(self) -> str:
        parts = [f"Goal ({self.category}): {self.title}."]
        if self.description:
            parts.append(self.description)
        parts.append(f"Status: {self.status.value}. Priority: {self.priority}. Progress: {self.progress:.0f}%.")
        return " ".join(parts)


@dataclass(frozen=True)
class GoalProgressUpdate:
    """A progress update on an existing goal - remembered as its own,
    new memory entry (append-only, matching the platform's semantic-
    retrieval-only memory model - see Architecture.md §9's rejection of
    in-place mutation) rather than an edit to the original Goal entry."""

    goal_title: str
    note: str
    new_progress: float | None = None
    new_status: GoalStatus | None = None
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_GOAL

    def to_memory_content(self) -> str:
        parts = [f"Progress update on goal '{self.goal_title}': {self.note}"]
        if self.new_progress is not None:
            parts.append(f"Progress now {self.new_progress:.0f}%.")
        if self.new_status is not None:
            parts.append(f"Status now {self.new_status.value}.")
        return " ".join(parts)
