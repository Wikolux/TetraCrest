"""Strategy & Portfolio Specialist structured outputs (Milestone 6) -
mirrors Discovery's/Product Decision's/Delivery's own outputs.py precedent
exactly (Milestones 3-5): every type here is a synthesis/response-shaping
structure, never a memory type of its own. `RoadmapItem` and `Metric` are
Milestone 1's own types (shared/roadmap.py, shared/metric.py), written
here via ProfessionalMemoryService, never redefined. `Portfolio` is
likewise Milestone 1's own type (shared/portfolio.py), deliberately
memory-type-less per ADR-0006/Architecture §12 - reused via the
already-existing `ProfessionalMemoryService.remember_portfolio()`, never
given a new write path.

`StrategyRecommendation` is this milestone's evidence-discipline
enforcement type, structurally distinct from Product Decision's own
`RecommendationReport` (Milestone 4) in one deliberate way: it has no
`counterpoint` field. Architecture §12 and ARR's own non-responsibility
boundary are explicit that Strategy & Portfolio "does not itself decide a
single, one-off decision's outcome with counterpoint discipline" - that
structural rigor belongs exclusively to the Product Decision Specialist.
`StrategyRecommendation` still cannot be constructed without evidence (or
an explicit gap), assumptions, trade-offs, risks, a confidence value, and
a stated remaining uncertainty - "never fabricate strategy" is a property
of the type.

`PortfolioAssessment` is deliberately scoped to Architecture §12's own v1
boundary: a per-product inventory, never a cross-product comparison,
conflict detection, or resource-tradeoff score (that reasoning is a
"defined, ready extension... not v1 functionality," per Architecture §12
and Implementation_Plan.md's own Milestone 6 acceptance criteria). Its
`scope_note` field is required precisely so a partial or single-product
view is never silently presented as a complete portfolio analysis - the
exact anti-pattern ARR §9 names ("Presenting a single-product view as a
full portfolio analysis").
"""

from dataclasses import dataclass, field

from app.services.ai.agents.specialists.product_management.shared.decision_record import DecisionFramework


def _as_tuple(value) -> tuple:
    return value if isinstance(value, tuple) else tuple(value)


@dataclass(frozen=True)
class RoadmapEntry:
    title: str
    horizon: str
    rationale: str = ""

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("RoadmapEntry.title is required")
        if not self.horizon:
            raise ValueError("RoadmapEntry.horizon is required")


@dataclass(frozen=True)
class RoadmapRecommendation:
    items: tuple[RoadmapEntry, ...]
    tradeoffs: tuple[str, ...]
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", _as_tuple(self.items))
        if not self.items:
            raise ValueError("RoadmapRecommendation.items must not be empty")
        object.__setattr__(self, "tradeoffs", _as_tuple(self.tradeoffs))
        if not self.tradeoffs:
            raise ValueError(
                "RoadmapRecommendation.tradeoffs must not be empty - a sequenced roadmap must name its "
                "tradeoffs explicitly (Implementation_Plan.md Milestone 6 acceptance criteria)"
            )
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))


@dataclass(frozen=True)
class PrioritizedInitiative:
    name: str
    score: float | None = None
    rationale: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("PrioritizedInitiative.name is required")


@dataclass(frozen=True)
class InitiativeSequence:
    framework: DecisionFramework
    items: tuple[PrioritizedInitiative, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", _as_tuple(self.items))


@dataclass(frozen=True)
class OpportunityComparison:
    options: tuple[str, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", _as_tuple(self.options))
        if len(self.options) < 2:
            raise ValueError("OpportunityComparison.options must contain at least two opportunities to compare")
        object.__setattr__(self, "notes", _as_tuple(self.notes))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))


@dataclass(frozen=True)
class ProductVisionAssessment:
    vision_statement: str
    aligned_initiatives: tuple[str, ...] = field(default_factory=tuple)
    misaligned_initiatives: tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.vision_statement:
            raise ValueError("ProductVisionAssessment.vision_statement is required")
        object.__setattr__(self, "aligned_initiatives", _as_tuple(self.aligned_initiatives))
        object.__setattr__(self, "misaligned_initiatives", _as_tuple(self.misaligned_initiatives))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))


@dataclass(frozen=True)
class OKRAssessment:
    objective: str
    key_results: tuple[str, ...] = field(default_factory=tuple)
    north_star: str = ""
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.objective:
            raise ValueError("OKRAssessment.objective is required")
        object.__setattr__(self, "key_results", _as_tuple(self.key_results))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))


@dataclass(frozen=True)
class TradeoffAssessment:
    tradeoffs: tuple[str, ...]
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tradeoffs", _as_tuple(self.tradeoffs))
        if not self.tradeoffs:
            raise ValueError("TradeoffAssessment.tradeoffs must not be empty")
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))


@dataclass(frozen=True)
class StrategyRecommendation:
    recommendation: str
    assumptions: tuple[str, ...]
    trade_offs: tuple[str, ...]
    risks: tuple[str, ...]
    confidence: float
    remaining_uncertainty: str
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_gap: str = ""

    def __post_init__(self) -> None:
        if not self.recommendation:
            raise ValueError("StrategyRecommendation.recommendation is required")
        object.__setattr__(self, "assumptions", _as_tuple(self.assumptions))
        object.__setattr__(self, "trade_offs", _as_tuple(self.trade_offs))
        object.__setattr__(self, "risks", _as_tuple(self.risks))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        if not self.assumptions:
            raise ValueError("StrategyRecommendation.assumptions must not be empty - every assumption must be named")
        if not self.trade_offs:
            raise ValueError("StrategyRecommendation.trade_offs must not be empty - every trade-off must be named")
        if not self.risks:
            raise ValueError("StrategyRecommendation.risks must not be empty - every risk must be named")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("StrategyRecommendation.confidence must be between 0.0 and 1.0")
        if not self.remaining_uncertainty:
            raise ValueError("StrategyRecommendation.remaining_uncertainty is required - never fabricate strategy")
        if not self.evidence_ids and not self.evidence_gap:
            raise ValueError(
                "StrategyRecommendation must cite supporting evidence_ids or state an explicit evidence_gap "
                "- a recommendation may never be silently ungrounded"
            )


@dataclass(frozen=True)
class PortfolioAssessment:
    products: tuple[str, ...]
    per_product_notes: tuple[str, ...]
    scope_note: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "products", _as_tuple(self.products))
        if not self.products:
            raise ValueError("PortfolioAssessment.products must not be empty")
        object.__setattr__(self, "per_product_notes", _as_tuple(self.per_product_notes))
        if not self.scope_note:
            raise ValueError(
                "PortfolioAssessment.scope_note is required - a partial or single-product view must never "
                "be silently presented as a complete portfolio analysis (ARR §9)"
            )


@dataclass(frozen=True)
class StrategySummary:
    summary: str
    roadmap_item_count: int = 0
    metric_count: int = 0

    def __post_init__(self) -> None:
        if not self.summary:
            raise ValueError("StrategySummary.summary is required")
