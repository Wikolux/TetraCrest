"""Decision - the Executive's structured record of what it decided to do
for one request, and why.

A pure value object: nothing here decides anything on its own - the
Executive's planner constructs one of these, and the Dispatcher reads it
to decide which agent (if any) is required.
"""

import uuid
from dataclasses import dataclass, field
from types import MappingProxyType

from app.services.ai.agents.types import Metadata


@dataclass(frozen=True)
class Decision:
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reason: str = ""
    confidence: float = 1.0
    requires_memory: bool = False
    requires_runtime: bool = True
    requires_delegation: bool = False
    requires_tools: bool = False
    requires_web: bool = False
    selected_agent: str | None = None
    priority: int = 0
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
