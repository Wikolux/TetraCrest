"""Product Decision Specialist structured outputs (Milestone 4) - mirrors
Discovery's own outputs.py precedent exactly (Milestone 3): every type
here is a synthesis/response-shaping structure, never a memory type of its
own. Two of this milestone's twelve named outputs are deliberately NOT
redefined here:

- "Decision Record" is Milestone 1's own `DecisionRecord`
  (shared/decision_record.py), reused as-is - redefining it here would be
  exactly the kind of silent redesign the Development Guide forbids.
- "Product Decision" is realized as this module's own `ProductDecisionContext` -
  the decision as options/criteria/question, before a framework has been
  applied to it (Architecture §8's "structures the decision as options,
  criteria, and tradeoffs" step).

`RecommendationReport` is the sharpest evidence-discipline type in this
milestone: it cannot be constructed without every one of this milestone's
own "every recommendation MUST" requirements (evidence or an explicit
gap, assumptions, risks, trade-offs, expected impact, a confidence value,
and a statement of remaining uncertainty) - "never fabricate certainty" is
a property of the type, not a hope about the prompt, the same discipline
DiscoveryRecommendation (Milestone 3) already established for Discovery.
"""

from dataclasses import dataclass, field

from app.services.ai.agents.specialists.product_management.shared.decision_record import DecisionFramework


def _as_tuple(value) -> tuple:
    return value if isinstance(value, tuple) else tuple(value)


@dataclass(frozen=True)
class ProductDecisionContext:
    """"Product Decision" - the decision as stated, before a framework is
    applied (Architecture §8's first structuring step)."""

    question: str
    options: tuple[str, ...] = field(default_factory=tuple)
    criteria: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.question:
            raise ValueError("ProductDecisionContext.question is required")
        object.__setattr__(self, "options", _as_tuple(self.options))
        object.__setattr__(self, "criteria", _as_tuple(self.criteria))


@dataclass(frozen=True)
class PrioritizedItem:
    name: str
    score: float | None = None
    rationale: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("PrioritizedItem.name is required")


@dataclass(frozen=True)
class PrioritizationResult:
    framework: DecisionFramework
    items: tuple[PrioritizedItem, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", _as_tuple(self.items))


@dataclass(frozen=True)
class FrameworkAnalysis:
    framework: DecisionFramework
    approach_notes: str
    score: float | None = None
    category: str = ""

    def __post_init__(self) -> None:
        if not self.approach_notes:
            raise ValueError("FrameworkAnalysis.approach_notes is required")


@dataclass(frozen=True)
class TradeoffReport:
    tradeoffs: tuple[str, ...]
    leans_toward: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "tradeoffs", _as_tuple(self.tradeoffs))
        if not self.tradeoffs:
            raise ValueError("TradeoffReport.tradeoffs must not be empty")


@dataclass(frozen=True)
class RiskItem:
    description: str
    likelihood: str = "unknown"
    impact: str = "unknown"

    def __post_init__(self) -> None:
        if not self.description:
            raise ValueError("RiskItem.description is required")


@dataclass(frozen=True)
class RiskAssessment:
    risks: tuple[RiskItem, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "risks", _as_tuple(self.risks))
        if not self.risks:
            raise ValueError("RiskAssessment.risks must not be empty")


@dataclass(frozen=True)
class ConfidenceAssessment:
    confidence: float
    rationale: str
    remaining_uncertainty: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("ConfidenceAssessment.confidence must be between 0.0 and 1.0")
        if not self.rationale:
            raise ValueError("ConfidenceAssessment.rationale is required - a confidence value must be justified")
        if not self.remaining_uncertainty:
            raise ValueError(
                "ConfidenceAssessment.remaining_uncertainty is required - never fabricate certainty by "
                "leaving residual uncertainty unstated"
            )


@dataclass(frozen=True)
class RecommendationReport:
    recommendation: str
    framework: DecisionFramework
    assumptions: tuple[str, ...]
    risks: tuple[str, ...]
    tradeoffs: tuple[str, ...]
    expected_impact: str
    confidence: float
    remaining_uncertainty: str
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_gap: str = ""

    def __post_init__(self) -> None:
        if not self.recommendation:
            raise ValueError("RecommendationReport.recommendation is required")
        object.__setattr__(self, "assumptions", _as_tuple(self.assumptions))
        object.__setattr__(self, "risks", _as_tuple(self.risks))
        object.__setattr__(self, "tradeoffs", _as_tuple(self.tradeoffs))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        if not self.assumptions:
            raise ValueError("RecommendationReport.assumptions must not be empty - every assumption must be named")
        if not self.risks:
            raise ValueError("RecommendationReport.risks must not be empty - every risk must be named")
        if not self.tradeoffs:
            raise ValueError("RecommendationReport.tradeoffs must not be empty - every trade-off must be named")
        if not self.expected_impact:
            raise ValueError("RecommendationReport.expected_impact is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("RecommendationReport.confidence must be between 0.0 and 1.0")
        if not self.remaining_uncertainty:
            raise ValueError(
                "RecommendationReport.remaining_uncertainty is required - never fabricate certainty"
            )
        if not self.evidence_ids and not self.evidence_gap:
            raise ValueError(
                "RecommendationReport must cite supporting evidence_ids or state an explicit evidence_gap "
                "- a recommendation may never be silently ungrounded"
            )


@dataclass(frozen=True)
class OptionScore:
    name: str
    score: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("OptionScore.name is required")


@dataclass(frozen=True)
class AlternativeComparison:
    options: tuple[OptionScore, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", _as_tuple(self.options))
        if len(self.options) < 2:
            raise ValueError("AlternativeComparison.options must contain at least two alternatives to compare")


@dataclass(frozen=True)
class DecisionSummary:
    title: str
    framework: str
    summary: str

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("DecisionSummary.title is required")
        if not self.summary:
            raise ValueError("DecisionSummary.summary is required")


@dataclass(frozen=True)
class DecisionReview:
    title: str
    original_outcome: str
    review_notes: str

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("DecisionReview.title is required")
        if not self.review_notes:
            raise ValueError("DecisionReview.review_notes is required")


@dataclass(frozen=True)
class DecisionHistorySummary:
    summary: str
    decision_count: int = 0
    frameworks_used: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.summary:
            raise ValueError("DecisionHistorySummary.summary is required")
        object.__setattr__(self, "frameworks_used", _as_tuple(self.frameworks_used))
