"""ResearchReport - the structured output of one research cycle.
Immutable, like every value object in this platform.
"""

from dataclasses import dataclass, field
from types import MappingProxyType

from app.services.ai.agents.types import Metadata


@dataclass(frozen=True)
class ResearchReport:
    executive_summary: str
    detailed_findings: tuple[str, ...] = field(default_factory=tuple)
    evidence: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0
    knowledge_gaps: tuple[str, ...] = field(default_factory=tuple)
    recommended_next_actions: tuple[str, ...] = field(default_factory=tuple)
    references: tuple[str, ...] = field(default_factory=tuple)
    appendices: tuple[str, ...] = field(default_factory=tuple)
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        for tuple_field in (
            "detailed_findings",
            "evidence",
            "knowledge_gaps",
            "recommended_next_actions",
            "references",
            "appendices",
        ):
            value = getattr(self, tuple_field)
            if not isinstance(value, tuple):
                object.__setattr__(self, tuple_field, tuple(value))
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
