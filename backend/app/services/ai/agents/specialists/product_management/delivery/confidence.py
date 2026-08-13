"""build_confidence_score() - the one, deterministic scoring function
behind every DeliveryConfidenceScore this specialist produces. A plain
count of satisfied checkable factors, expressed as a percentage - never a
model-generated probability ("explanatory, not probabilistic AI
confidence," this milestone's own governing instruction). Mirrors
scoring.py's own RICE/ICE precedent (Milestone 4): real arithmetic over
real inputs, never an invented number.
"""

from app.services.ai.agents.specialists.product_management.delivery.outputs import ConfidenceFactor, DeliveryConfidenceScore


def build_confidence_score(factors: tuple[ConfidenceFactor, ...]) -> DeliveryConfidenceScore:
    satisfied = sum(1 for factor in factors if factor.satisfied)
    percent = round(100 * satisfied / len(factors)) if factors else 0
    return DeliveryConfidenceScore(score_percent=percent, factors=factors)
