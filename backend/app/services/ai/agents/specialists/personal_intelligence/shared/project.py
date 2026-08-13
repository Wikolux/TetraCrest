"""Project - a persistent project the user is working on."""

from dataclasses import dataclass, field
from datetime import datetime

from app.services.ai.agents.specialists.personal_intelligence.shared.types import MEMORY_TYPE_PROJECT


@dataclass(frozen=True)
class Project:
    name: str
    objective: str = ""
    milestones: tuple[str, ...] = field(default_factory=tuple)
    progress: float = 0.0
    active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    memory_type = MEMORY_TYPE_PROJECT

    def __post_init__(self) -> None:
        if not isinstance(self.milestones, tuple):
            object.__setattr__(self, "milestones", tuple(self.milestones))
        if not 0.0 <= self.progress <= 100.0:
            raise ValueError(f"Project.progress must be between 0 and 100, got {self.progress}")

    def to_memory_content(self) -> str:
        parts = [f"Project: {self.name}."]
        if self.objective:
            parts.append(f"Objective: {self.objective}.")
        if self.milestones:
            parts.append("Milestones: " + "; ".join(self.milestones) + ".")
        parts.append(f"Active: {self.active}. Progress: {self.progress:.0f}%.")
        return " ".join(parts)
