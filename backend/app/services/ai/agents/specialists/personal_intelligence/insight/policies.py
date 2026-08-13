"""InsightPolicy - domain-specific policy for the Insight Engine
specialist, layered on top of (never duplicating) SpecialistExecutionPolicy
(which already owns maximum_depth/timeout_seconds/retry_policy - see
app.services.ai.agents.specialists.shared.policies), mirroring
PersonalIntelligencePolicy's/ResearchPolicy's exact precedent. Holds only
what's genuinely specific to insight generation: how much of a user's
memory corpus to analyze, the thresholds a term must cross to count as a
pattern/habit, and the confidence floor for a response to be considered
acceptable.
"""

from dataclasses import dataclass

__all__ = ["InsightPolicy"]


@dataclass(frozen=True)
class InsightPolicy:
    default_lookback_days: int = 30
    default_maximum_memories_analyzed: int = 200
    default_pattern_minimum_occurrences: int = 3
    default_habit_minimum_occurrences: int = 2
    default_recall_limit: int = 10
    default_max_context_tokens: int = 4000
    minimum_confidence: float = 0.0
