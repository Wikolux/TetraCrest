"""DeliveryPolicy - domain-specific policy for the Delivery Specialist,
mirroring DiscoveryPolicy/DecisionPolicy exactly: layered on top of, not
duplicating, SpecialistExecutionPolicy.
"""

from dataclasses import dataclass

__all__ = ["DeliveryPolicy"]


@dataclass(frozen=True)
class DeliveryPolicy:
    default_recall_limit: int = 10
    default_max_context_tokens: int = 4000
    default_list_maximum: int = 50
    minimum_confidence: float = 0.0
