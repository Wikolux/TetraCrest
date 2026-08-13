"""DecisionPolicy - domain-specific policy for the Product Decision
Specialist, mirroring DiscoveryPolicy/ResearchPolicy exactly: layered on
top of, not duplicating, SpecialistExecutionPolicy.
"""

from dataclasses import dataclass

__all__ = ["DecisionPolicy"]


@dataclass(frozen=True)
class DecisionPolicy:
    default_recall_limit: int = 10
    default_max_context_tokens: int = 4000
    default_list_maximum: int = 50
    minimum_confidence: float = 0.0
