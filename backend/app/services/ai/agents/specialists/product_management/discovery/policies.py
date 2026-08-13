"""DiscoveryPolicy - domain-specific policy for the Discovery Specialist,
mirroring ResearchPolicy/PersonalIntelligencePolicy exactly: layered on
top of, not duplicating, SpecialistExecutionPolicy (which already owns
maximum_depth/timeout_seconds/retry_policy). Holds only what's genuinely
specific to Discovery: how much precedent to retrieve by default, and the
confidence floor for a response to be considered acceptable.

minimum_confidence defaults to 0.0 (identical to every existing specialist
policy) - Discovery's own honesty discipline is enforced structurally, by
DiscoveryRecommendation's own construction-time evidence requirement
(outputs.py), not by refusing to return a low-confidence response. A
low-confidence, evidence-gap-disclosing response is Discovery working
correctly (ARR §8), never a response this policy should suppress.
"""

from dataclasses import dataclass

__all__ = ["DiscoveryPolicy"]


@dataclass(frozen=True)
class DiscoveryPolicy:
    default_recall_limit: int = 10
    default_max_context_tokens: int = 4000
    default_list_maximum: int = 50
    minimum_confidence: float = 0.0
