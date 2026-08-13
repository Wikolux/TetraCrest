"""StrategyRequest - what a caller asks the Strategy & Portfolio
Specialist to do. Mirrors DiscoveryRequest's/DecisionRequest's/
DeliveryRequest's own precedent exactly (Milestones 3-5).

The operation set maps directly onto PRD §17/§19's approved capabilities.
`ASSESS_PORTFOLIO` is deliberately the only portfolio-grain operation, and
is scoped to a per-product inventory only - see outputs.py's own
`PortfolioAssessment` docstring for the exact v1 boundary this respects
(Architecture §12, Implementation_Plan.md Milestone 6). `products` is the
one field genuinely specific to that operation; every other field mirrors
the established shape from prior specialists.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class StrategyOperation(StrEnum):
    SEQUENCE_ROADMAP = "sequence_roadmap"
    PRIORITIZE_INITIATIVES = "prioritize_initiatives"
    COMPARE_OPPORTUNITIES = "compare_opportunities"
    ASSESS_VISION_ALIGNMENT = "assess_vision_alignment"
    STRUCTURE_NORTH_STAR = "structure_north_star"
    STRUCTURE_OKRS = "structure_okrs"
    ASSESS_TRADEOFFS = "assess_tradeoffs"
    GENERATE_RECOMMENDATION = "generate_recommendation"
    ASSESS_PORTFOLIO = "assess_portfolio"
    SUMMARIZE_STRATEGY = "summarize_strategy"
    RECALL = "recall"


@dataclass(frozen=True)
class StrategyRequest:
    operation: StrategyOperation
    text: str = ""
    title: str = ""
    framework: str = ""
    items: tuple[str, ...] = field(default_factory=tuple)
    products: tuple[str, ...] = field(default_factory=tuple)
    key_results: tuple[str, ...] = field(default_factory=tuple)
    product_name: str = ""
    horizon: str = ""
    reach: float | None = None
    impact: float | None = None
    confidence_input: float | None = None
    effort: float | None = None
    ease: float | None = None

    def __post_init__(self) -> None:
        for name in ("items", "products", "key_results"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
