"""DecisionRecord - a structured product decision and its outcome
(Architecture §7); the backbone of Product Decision Support's
precedent-surfacing (Architecture §8).

This is the entity ARR §7 named explicitly: "Phase 3 must build the
Decision Record ... with the identical structural-enforcement pattern
Insight already proved out - evidence references required at
construction, not merely recommended by convention." Three fields are
therefore required, not optional, each tracing to a different governing
requirement rather than being bundled together as one vague "be
thorough" rule:

- `framework` (no default): Architecture §14's own quality rubric - "a
  Decision Support recommendation is incomplete without a named
  framework."
- `counterpoint` (must be non-empty): Architecture §8 - "the counterpoint
  step is not optional ... it must run before a recommendation is
  produced, never appended after."
- `supporting_memory_ids` (must be non-empty): ARR §7's own finding -
  evidence references required at construction, mirroring exactly how
  CP-01.3's `Insight.supporting_memory_ids` makes a claim's evidence
  structurally undeniable rather than merely documented.

A DecisionRecord that cannot state what evidence grounded it, what
framework structured it, and what counterpoint was weighed against it is
not a decision this pack is permitted to construct - not as a matter of
convention, but as a matter of what Python will let the caller do.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_DECISION


class DecisionFramework(StrEnum):
    RICE = "rice"
    ICE = "ice"
    KANO = "kano"
    COST_OF_DELAY = "cost_of_delay"
    BUILD_VS_BUY = "build_vs_buy"
    SUNSET_CHECKLIST = "sunset_checklist"


@dataclass(frozen=True)
class DecisionRecord:
    title: str
    framework: DecisionFramework
    rationale: str
    counterpoint: str
    supporting_memory_ids: tuple[int, ...]
    options_considered: tuple[str, ...] = field(default_factory=tuple)
    outcome: str = ""
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_DECISION

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("DecisionRecord.title is required")
        if not isinstance(self.supporting_memory_ids, tuple):
            object.__setattr__(self, "supporting_memory_ids", tuple(self.supporting_memory_ids))
        if not isinstance(self.options_considered, tuple):
            object.__setattr__(self, "options_considered", tuple(self.options_considered))
        if not self.rationale:
            raise ValueError("DecisionRecord.rationale is required")
        if not self.counterpoint:
            raise ValueError(
                "DecisionRecord.counterpoint is required - Architecture §8 requires every decision to "
                "surface a counterpoint before it is recorded, never as an afterthought"
            )
        if not self.supporting_memory_ids:
            raise ValueError(
                "DecisionRecord.supporting_memory_ids is required - a decision must be traceable to the "
                "evidence that grounded it (ARR §7)"
            )

    def to_memory_content(self) -> str:
        parts = [f"Decision: {self.title}.", f"Framework applied: {self.framework.value}."]
        if self.options_considered:
            parts.append("Options considered: " + "; ".join(self.options_considered) + ".")
        parts.append(f"Rationale: {self.rationale}")
        parts.append(f"Counterpoint considered: {self.counterpoint}")
        ids = ", ".join(str(i) for i in self.supporting_memory_ids)
        parts.append(f"Supporting evidence: {ids}.")
        if self.outcome:
            parts.append(f"Outcome: {self.outcome}")
        return " ".join(parts)
