"""Pure RICE/ICE scoring functions - deterministic arithmetic, never
Runtime-generated, so a numeric score is either genuinely computed from
real inputs or explicitly absent (never approximated, never invented).
Mirrors the platform-wide "deterministic, not adaptive" philosophy every
existing planner already follows (ExecutivePlanner, ResearchPlanner).

Framework selection (which of the six approved DecisionFrameworks fits a
given decision's shape) is Architecture §8's own structural discipline,
realized here as plain, testable functions rather than folded invisibly
into the specialist's own control flow.
"""

from app.services.ai.agents.specialists.product_management.shared.decision_record import DecisionFramework

_SUNSET_KEYWORDS = ("sunset", "deprecat", "retire", "shut down", "shutdown")
_BUILD_VS_BUY_KEYWORDS = ("build vs buy", "build or buy", "vendor", "outsource", "partner")
_COST_OF_DELAY_KEYWORDS = ("cost of delay", "sequenc", "urgen", "wsjf", "delay")
_KANO_KEYWORDS = ("kano", "delight", "must-have", "must have", "performance feature")


def select_framework(text: str, option_count: int) -> DecisionFramework:
    """Architecture §8's framework-selection discipline, made concrete:
    a backlog-ranking decision reaches for RICE/ICE/Kano; a sourcing
    decision reaches for build-vs-buy; a sequencing decision reaches for
    Cost of Delay; a deprecation call reaches for a sunset checklist.
    ICE is the default - the simplest, always-applicable prioritization
    framework - when nothing more specific is indicated."""
    lowered = text.lower()
    if any(keyword in lowered for keyword in _SUNSET_KEYWORDS):
        return DecisionFramework.SUNSET_CHECKLIST
    if any(keyword in lowered for keyword in _BUILD_VS_BUY_KEYWORDS):
        return DecisionFramework.BUILD_VS_BUY
    if any(keyword in lowered for keyword in _COST_OF_DELAY_KEYWORDS):
        return DecisionFramework.COST_OF_DELAY
    if any(keyword in lowered for keyword in _KANO_KEYWORDS):
        return DecisionFramework.KANO
    if option_count > 2:
        return DecisionFramework.RICE
    return DecisionFramework.ICE


def rice_score(reach: float | None, impact: float | None, confidence: float | None, effort: float | None) -> float | None:
    """RICE = (Reach x Impact x Confidence) / Effort - a weighted-scoring
    approach (this milestone's own "Weighted Scoring" and "Impact vs
    Effort" reasoning, applied concretely rather than left as vocabulary).
    None whenever any input, or effort=0, would make the result
    fabricated rather than computed."""
    if reach is None or impact is None or confidence is None or effort is None or effort == 0:
        return None
    return (reach * impact * confidence) / effort


def ice_score(impact: float | None, confidence: float | None, ease: float | None) -> float | None:
    """ICE = mean(Impact, Confidence, Ease) - the same Impact-vs-Effort
    (Ease is effort inverted) reasoning this milestone names, applied as
    real arithmetic rather than merely as a label."""
    if impact is None or confidence is None or ease is None:
        return None
    return (impact + confidence + ease) / 3
