"""PMCraftRecord - which framework was applied to which decision, and
with how much supporting evidence (Architecture §6/§13): a byproduct of
ordinary Decision Support work, feeding the later, v3-scoped Career
Development mode without requiring new capture when that mode is built
(Architecture §13: "Career Development does not require new capture, only
new reasoning over what's already captured").

Added at Milestone 4, per shared/types.py's own documented deferral - this
is Architecture §6's originally-approved PM Craft Record category, not a
new memory-type decision (no ADR required, ARR §4 Ownership Matrix already
assigns it to the Product Decision Specialist).

`framework` and `decision_title` are both required, mirroring the same
construction-time discipline every other Milestone 1 evidence-adjacent
type already applies: a craft record that cannot say which framework was
actually applied, to which decision, is not evidence of applied craft -
it is an unsupported claim of rigor.
"""

from dataclasses import dataclass
from datetime import datetime

from app.services.ai.agents.specialists.product_management.shared.decision_record import DecisionFramework
from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_PM_CRAFT_RECORD


@dataclass(frozen=True)
class PMCraftRecord:
    framework: DecisionFramework
    decision_title: str
    evidence_count: int = 0
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_PM_CRAFT_RECORD

    def __post_init__(self) -> None:
        if not self.decision_title:
            raise ValueError("PMCraftRecord.decision_title is required - a craft record must trace to a real decision")

    def to_memory_content(self) -> str:
        content = f"Applied {self.framework.value} to decision: {self.decision_title}."
        if self.evidence_count:
            content += f" Grounded in {self.evidence_count} supporting evidence item(s)."
        return content
