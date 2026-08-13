"""Pure RICE/ICE scoring functions for backlog-wide prioritization
(PRD §17: "RICE... ICE... Kano... Cost of Delay/WSJF... are applied as
structuring tools over candidate initiatives"). Deterministic arithmetic,
never Runtime-generated - the identical "compute from real inputs or
state the absence honestly" discipline scoring.py (Product Decision
Specialist, Milestone 4) already established.

Independently defined here, not imported from
product_management.product_decision.scoring - this specialist never
imports Product Decision Specialist code (Pack Independence, restated for
CP-02-internal specialists by Implementation_Plan.md §3). RICE and ICE are
public, standard prioritization formulas (Architecture §8/§14), not a
private algorithm unique to either specialist - each specialist owning an
identical, independently-written implementation of a public formula is
not code duplication in the sense the platform's reuse discipline forbids;
it is the same discipline CP-01 and CP-02 each independently implementing
their own memory-type namespace convention already reflects.

Framework selection reuses Milestone 1's own `DecisionFramework` enum
(shared/decision_record.py) directly - that type is a shared, pack-level
domain object, not owned by the Product Decision Specialist's package, so
importing it is ordinary Milestone 1 domain-model reuse, not a
specialist-to-specialist import.
"""

from app.services.ai.agents.specialists.product_management.shared.decision_record import DecisionFramework

_SUNSET_KEYWORDS = ("sunset", "deprecat", "retire", "shut down", "shutdown")
_INVESTMENT_KEYWORDS = ("invest", "fund", "double down", "build vs buy", "build or buy", "vendor", "outsource")
_COST_OF_DELAY_KEYWORDS = ("cost of delay", "sequenc", "urgen", "wsjf", "delay")
_KANO_KEYWORDS = ("kano", "delight", "must-have", "must have", "performance feature")


def select_framework(text: str, option_count: int) -> DecisionFramework:
    """Strategy's own framework-selection discipline, at backlog-wide
    grain (PRD §17) rather than Product Decision Support's one-off grain
    (Architecture §8) - the same structural principle ("the framework
    fits the decision"), applied over candidate initiatives instead of a
    single decision. ICE is the default when nothing more specific is
    indicated - the simplest, always-applicable prioritization framework."""
    lowered = text.lower()
    if any(keyword in lowered for keyword in _SUNSET_KEYWORDS):
        return DecisionFramework.SUNSET_CHECKLIST
    if any(keyword in lowered for keyword in _INVESTMENT_KEYWORDS):
        return DecisionFramework.BUILD_VS_BUY
    if any(keyword in lowered for keyword in _COST_OF_DELAY_KEYWORDS):
        return DecisionFramework.COST_OF_DELAY
    if any(keyword in lowered for keyword in _KANO_KEYWORDS):
        return DecisionFramework.KANO
    if option_count > 2:
        return DecisionFramework.RICE
    return DecisionFramework.ICE


def rice_score(reach: float | None, impact: float | None, confidence: float | None, effort: float | None) -> float | None:
    """RICE = (Reach x Impact x Confidence) / Effort. None whenever any
    input, or effort=0, would make the result fabricated rather than
    computed."""
    if reach is None or impact is None or confidence is None or effort is None or effort == 0:
        return None
    return (reach * impact * confidence) / effort


def ice_score(impact: float | None, confidence: float | None, ease: float | None) -> float | None:
    """ICE = mean(Impact, Confidence, Ease)."""
    if impact is None or confidence is None or ease is None:
        return None
    return (impact + confidence + ease) / 3
