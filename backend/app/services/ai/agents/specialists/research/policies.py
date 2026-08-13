"""ResearchPolicy - research-specific execution policy, layered on top of
(not duplicating) app.services.ai.agents.specialists.shared.policies.SpecialistExecutionPolicy,
the same way app.services.ai.agents.executive.policies.ExecutivePolicy is
its own thing distinct from the generic agent-level policies.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchPolicy:
    maximum_sources: int = 10
    minimum_confidence: float = 0.0
    require_evidence: bool = False
