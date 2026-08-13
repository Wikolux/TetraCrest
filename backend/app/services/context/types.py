from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


class RankedResult(Protocol):
    """Structural shape ContextBuilder.build() needs from each ranked result.

    Deliberately not app.services.ranking.types.RankedCandidate - that
    type carries no `content` (ranking doesn't need it to compute a
    score), so it can't fully satisfy ContextItem's fields yet. This
    Protocol documents the shape ContextBuilder actually consumes -
    anything with these attributes works (a real future integration type,
    a test fake, ...) without Context Builder importing anything from the
    ranking package. Wiring the real ranking output into this shape is the
    integration milestone's job, not this one's.
    """

    resource_type: str
    resource_id: int
    content: str
    score: float
    created_at: datetime
    metadata: dict | None


@dataclass
class ContextItem:
    """One retrieved item, ready to flow through the context pipeline."""

    resource_type: str
    resource_id: int
    content: str
    score: float
    created_at: datetime
    metadata: dict | None = None


@dataclass
class ContextSection:
    """All ContextItems of one resource_type, grouped together."""

    resource_type: str
    items: list[ContextItem] = field(default_factory=list)


@dataclass
class ContextPackage:
    """The Context Builder's final output - what a future Prompt Builder
    will consume. Contains no markdown, no prompt text, nothing
    LLM-specific: purely structured data."""

    sections: list[ContextSection]
    estimated_tokens: int
    item_count: int
    truncated: bool


@dataclass
class BudgetedItems:
    """Internal pipeline-only carrier: BudgetStage's output.

    An ordered, possibly-truncated ContextItem list plus the token
    accounting later stages need - never returned to a ContextBuilder
    caller directly (FormatterStage's ContextPackage is the only public
    output type).
    """

    items: list[ContextItem]
    estimated_tokens: int
    truncated: bool


@dataclass
class GroupedItems:
    """Internal pipeline-only carrier: GroupingStage's output.

    ContextItems bucketed by resource_type (dict insertion order gives
    deterministic "groups ordered by first appearance"), with the token
    accounting carried forward unchanged from BudgetStage.
    """

    groups: dict[str, list[ContextItem]]
    estimated_tokens: int
    truncated: bool
