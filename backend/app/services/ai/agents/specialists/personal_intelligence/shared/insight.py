"""Insight - one unit of derived personal understanding: a recurring
pattern, a behavioral habit, a contradiction, a goal-alignment reading, a
periodic reflection, a proactive recommendation, or a profile summary.

The central discipline this type exists to enforce: **every Insight
carries its own evidence**. `observation` is always the literal, mechanical
fact the Insight Engine counted or matched (a raw count, a keyword hit) -
never invented, never adjusted for narrative flow. `basis` says plainly
whether `observation` IS the whole story (OBSERVED) or whether a further,
human-readable judgment was drawn from it (INFERRED, in which case
`conclusion` holds that judgment, kept visibly separate from the
observation it was drawn from). `supporting_memory_ids` is the exact set
of Memory row ids (ContextItem.resource_id) the Insight was computed from -
always sufficient for a caller to go look at the original memories an
Insight is claiming to be about. It is empty only for the honest "there
was nothing to observe" case (e.g. a periodic reflection computed over a
window with zero memories in it) - never because evidence was omitted for
a claim that needed it. This is what makes "every generated insight must
be traceable back to supporting memories rather than invented" true by
construction, not by convention.

Like every other CP-01 domain object, `to_memory_content()` renders this
as natural-language prose - the only "structured storage" available, since
the Memory model has no metadata column (see shared/types.py) - and
`memory_type` tags it `personal_insight` so it is trivially excluded from
the raw corpus a future analysis pass would otherwise re-analyze.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.services.ai.agents.specialists.personal_intelligence.shared.types import MEMORY_TYPE_INSIGHT


class InsightType(StrEnum):
    PATTERN = "pattern"
    HABIT = "habit"
    CONTRADICTION = "contradiction"
    ALIGNMENT = "alignment"
    PERIODIC_REFLECTION = "periodic_reflection"
    RECOMMENDATION = "recommendation"
    PROFILE_SUMMARY = "profile_summary"


class InsightBasis(StrEnum):
    """Whether an Insight's content is a plain observed fact, or a
    judgment inferred from one or more observed facts. Both remain fully
    traceable via supporting_memory_ids either way - this distinguishes
    *what kind of claim* an Insight is making, not how well-evidenced it
    is (that's `confidence`)."""

    OBSERVED = "observed"
    INFERRED = "inferred"


class InsightPeriod(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass(frozen=True)
class Insight:
    insight_type: InsightType
    title: str
    observation: str
    basis: InsightBasis = InsightBasis.OBSERVED
    conclusion: str = ""
    supporting_memory_ids: tuple[int, ...] = field(default_factory=tuple)
    confidence: float = 1.0
    subject: str = ""
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_INSIGHT

    def __post_init__(self) -> None:
        if not isinstance(self.supporting_memory_ids, tuple):
            object.__setattr__(self, "supporting_memory_ids", tuple(self.supporting_memory_ids))
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Insight.confidence must be between 0 and 1, got {self.confidence}")
        if self.basis == InsightBasis.INFERRED and not self.conclusion:
            raise ValueError("An INFERRED Insight must state its conclusion, not just its observation")

    def to_memory_content(self) -> str:
        parts = [f"Insight ({self.insight_type.value}): {self.title}.", f"Observed: {self.observation}"]
        if self.basis == InsightBasis.INFERRED:
            parts.append(f"Inferred: {self.conclusion}")
        if self.supporting_memory_ids:
            ids = ", ".join(str(i) for i in self.supporting_memory_ids)
            parts.append(f"Supporting memories: {ids}.")
        return " ".join(parts)
