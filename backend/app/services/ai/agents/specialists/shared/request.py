"""SpecialistRequest - what a caller (the Executive, or any future
delegator) asks a specialist to do. Deliberately generic across every
specialist domain - Research today, Finance/Trading/Vision/... future -
none of these fields are research-specific.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SpecialistRequest:
    objective: str
    constraints: tuple[str, ...] = field(default_factory=tuple)
    priority: int = 0
    deadline: datetime | None = None
    expected_output: str = ""
    context: str = ""
    tools_allowed: bool = True
    memory_allowed: bool = True
    web_allowed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.constraints, tuple):
            object.__setattr__(self, "constraints", tuple(self.constraints))
