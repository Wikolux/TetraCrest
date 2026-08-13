"""PersonalIntelligenceRequest - what a caller asks the Personal
Intelligence specialist to do.

Not a duplicate of SpecialistRequest (app.services.ai.agents.specialists.shared.request)
- that type is the Specialist Framework's generic, cross-domain request
shape (objective/constraints/priority/...), and it has no slot for "which
structured operation" or the typed hints (title/priority/status) CP-01's
write-side operations need. Building a pack-local request type when the
shared generic genuinely doesn't fit is the same, sanctioned pattern
Vision's VisionRequest and the Executive's own Decision/Task types already
follow - see docs/08_CAPABILITY_PACKS/CP-01_Personal_Intelligence_Pack/Architecture.md §8.
PersonalIntelligenceAgent's rich entry point takes this type directly,
the same way ResearchAgent.research() takes a SpecialistRequest directly -
SpecialistContext.request remains SpecialistRequest | None, untouched.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class PersonalIntelligenceOperation(StrEnum):
    REMEMBER_IDENTITY = "remember_identity"
    REMEMBER_GOAL = "remember_goal"
    UPDATE_GOAL_PROGRESS = "update_goal_progress"
    REMEMBER_PROJECT = "remember_project"
    REMEMBER_REFLECTION = "remember_reflection"
    REMEMBER_PREFERENCE = "remember_preference"
    RECALL = "recall"


@dataclass(frozen=True)
class PersonalIntelligenceRequest:
    operation: PersonalIntelligenceOperation
    text: str = ""
    title: str = ""
    category: str = ""
    priority: int = 0
    progress: float | None = None
    status: str = ""
    milestones: tuple[str, ...] = field(default_factory=tuple)
    lessons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.milestones, tuple):
            object.__setattr__(self, "milestones", tuple(self.milestones))
        if not isinstance(self.lessons, tuple):
            object.__setattr__(self, "lessons", tuple(self.lessons))
