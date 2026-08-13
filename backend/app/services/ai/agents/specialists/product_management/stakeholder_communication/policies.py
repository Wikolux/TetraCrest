"""CommunicationPolicy - domain-specific policy for the Stakeholder
Communication Specialist, mirroring DiscoveryPolicy/DecisionPolicy/
DeliveryPolicy/StrategyPolicy exactly: layered on top of, not duplicating,
SpecialistExecutionPolicy.
"""

from dataclasses import dataclass

__all__ = ["CommunicationPolicy"]


@dataclass(frozen=True)
class CommunicationPolicy:
    default_recall_limit: int = 10
    default_max_context_tokens: int = 4000
    default_list_maximum: int = 50
    minimum_confidence: float = 0.0
