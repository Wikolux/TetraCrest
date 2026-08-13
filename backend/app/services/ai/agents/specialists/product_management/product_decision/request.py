"""DecisionRequest - what a caller asks the Product Decision Specialist to
do. Mirrors DiscoveryRequest's own precedent exactly (Milestone 3): a
pack-local request type built because SpecialistRequest genuinely doesn't
carry a slot for "which structured operation" or this specialist's own
typed hints (framework, options, criteria, assumptions, counterpoint, the
optional RICE/ICE numeric inputs).

The operation set maps directly onto this milestone's Primary
Responsibilities: PRIORITIZE_FEATURES, APPLY_FRAMEWORK, ANALYZE_TRADEOFFS,
COMPARE_OPTIONS, IDENTIFY_RISKS, VALIDATE_ASSUMPTIONS, ASSESS_CONFIDENCE,
GENERATE_RECOMMENDATION, SUMMARIZE_DECISION, RECALL_DECISION_HISTORY.
"Decision documentation" is realized as GENERATE_RECOMMENDATION's own
write path (the only operation with enough - framework, rationale,
counterpoint, evidence - to construct a valid DecisionRecord), not a
separate operation. "Opportunity scoring" reuses PRIORITIZE_FEATURES
against an opportunity-shaped `question`/`options` input rather than a
dedicated operation, since opportunity assessment itself remains the
Discovery Specialist's own, never recreated here.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class DecisionOperation(StrEnum):
    PRIORITIZE_FEATURES = "prioritize_features"
    APPLY_FRAMEWORK = "apply_framework"
    ANALYZE_TRADEOFFS = "analyze_tradeoffs"
    COMPARE_OPTIONS = "compare_options"
    IDENTIFY_RISKS = "identify_risks"
    VALIDATE_ASSUMPTIONS = "validate_assumptions"
    ASSESS_CONFIDENCE = "assess_confidence"
    GENERATE_RECOMMENDATION = "generate_recommendation"
    SUMMARIZE_DECISION = "summarize_decision"
    RECALL_DECISION_HISTORY = "recall_decision_history"


@dataclass(frozen=True)
class DecisionRequest:
    operation: DecisionOperation
    question: str = ""
    title: str = ""
    framework: str = ""
    options: tuple[str, ...] = field(default_factory=tuple)
    criteria: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    counterpoint: str = ""
    outcome: str = ""
    reach: float | None = None
    impact: float | None = None
    confidence_input: float | None = None
    effort: float | None = None
    ease: float | None = None

    def __post_init__(self) -> None:
        for name in ("options", "criteria", "assumptions"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
