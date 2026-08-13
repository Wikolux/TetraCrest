"""Reflection - one structured reflection entry (evening, weekly, or
ad hoc). Always a new memory - reflections are episodic by nature, never
updated in place.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.services.ai.agents.specialists.personal_intelligence.shared.types import MEMORY_TYPE_REFLECTION


class ReflectionPeriod(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    AD_HOC = "ad_hoc"


@dataclass(frozen=True)
class Reflection:
    content: str
    period: ReflectionPeriod = ReflectionPeriod.AD_HOC
    lessons: tuple[str, ...] = ()
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_REFLECTION

    def __post_init__(self) -> None:
        if not isinstance(self.lessons, tuple):
            object.__setattr__(self, "lessons", tuple(self.lessons))

    def to_memory_content(self) -> str:
        parts = [f"Reflection ({self.period.value}): {self.content}"]
        if self.lessons:
            parts.append("Lessons learned: " + "; ".join(self.lessons) + ".")
        return " ".join(parts)
