"""PersonalIntelligencePolicy - domain-specific policy for the Personal
Intelligence specialist, mirroring ResearchPolicy exactly: layered on top
of, not duplicating, SpecialistExecutionPolicy (which already owns
maximum_depth/timeout_seconds/retry_policy - see
app.services.ai.agents.specialists.shared.policies). This policy holds
only what's genuinely specific to Personal Intelligence: how much context
to recall by default, and the confidence floor for a response to be
considered acceptable.
"""

from dataclasses import dataclass

__all__ = ["PersonalIntelligencePolicy"]


@dataclass(frozen=True)
class PersonalIntelligencePolicy:
    default_recall_limit: int = 10
    default_max_context_tokens: int = 4000
    minimum_confidence: float = 0.0
