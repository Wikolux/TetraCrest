"""ResearchFinding - the synthesized output of a delegated research
question (Architecture §7, §9). "Never exists without a recorded source
question" is Architecture §7's own, explicit requirement - `source_question`
is therefore required at construction, the same structural-enforcement
discipline DiscoveryFinding applies to `source` and DecisionRecord applies
to its own evidence fields (ARR §7).

CP-02 never performs research itself (Implementation_Plan.md §10) - this
type exists purely to record what the existing ResearchAgent, delegated
to via the Executive, already returned. It is never constructed from
CP-02's own guesswork.
"""

from dataclasses import dataclass
from datetime import datetime

from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_RESEARCH_FINDING


@dataclass(frozen=True)
class ResearchFinding:
    summary: str
    source_question: str
    implications: str = ""
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_RESEARCH_FINDING

    def __post_init__(self) -> None:
        if not self.summary:
            raise ValueError("ResearchFinding.summary is required")
        if not self.source_question:
            raise ValueError(
                "ResearchFinding.source_question is required - a research finding must reference the "
                "question that produced it (Architecture §7)"
            )

    def to_memory_content(self) -> str:
        parts = [f"Research finding (re: '{self.source_question}'): {self.summary}"]
        if self.implications:
            parts.append(f"Implications: {self.implications}")
        return " ".join(parts)
