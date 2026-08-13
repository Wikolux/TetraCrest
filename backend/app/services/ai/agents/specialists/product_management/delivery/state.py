"""DeliveryState - identical topology to DiscoveryState/DecisionState
(Milestones 3-4), which itself realizes CP-02 Architecture §16's shared,
cross-specialist state topology.
"""

from enum import StrEnum

from app.services.ai.agents.types import AgentError


class DeliveryState(StrEnum):
    IDLE = "idle"
    INTERPRETING = "interpreting"
    GATHERING = "gathering"
    STRUCTURING = "structuring"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


_VALID_TRANSITIONS: dict[DeliveryState, frozenset[DeliveryState]] = {
    DeliveryState.IDLE: frozenset({DeliveryState.INTERPRETING, DeliveryState.FAILED}),
    DeliveryState.INTERPRETING: frozenset(
        {DeliveryState.GATHERING, DeliveryState.STRUCTURING, DeliveryState.FAILED}
    ),
    DeliveryState.GATHERING: frozenset({DeliveryState.STRUCTURING, DeliveryState.FAILED}),
    DeliveryState.STRUCTURING: frozenset({DeliveryState.SYNTHESIZING, DeliveryState.FAILED}),
    DeliveryState.SYNTHESIZING: frozenset({DeliveryState.COMPLETED, DeliveryState.FAILED}),
    DeliveryState.COMPLETED: frozenset({DeliveryState.IDLE}),
    DeliveryState.FAILED: frozenset({DeliveryState.IDLE}),
}


class InvalidDeliveryStateTransitionError(AgentError):
    """Raised when a DeliveryState transition is not allowed from the
    current state."""


class DeliveryStateMachine:
    def __init__(self, initial: DeliveryState = DeliveryState.IDLE) -> None:
        self._state = initial

    @property
    def state(self) -> DeliveryState:
        return self._state

    def can_transition(self, target: DeliveryState) -> bool:
        return target in _VALID_TRANSITIONS.get(self._state, frozenset())

    def transition(self, target: DeliveryState) -> None:
        if not self.can_transition(target):
            raise InvalidDeliveryStateTransitionError(f"Cannot transition from {self._state} to {target}")
        self._state = target
