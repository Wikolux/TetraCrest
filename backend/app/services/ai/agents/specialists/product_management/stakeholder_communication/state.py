"""CommunicationState - identical topology to DiscoveryState/DecisionState/
DeliveryState/StrategyState (Milestones 3-6), which itself realizes CP-02
Architecture §16's shared, cross-specialist state topology.
"""

from enum import StrEnum

from app.services.ai.agents.types import AgentError


class CommunicationState(StrEnum):
    IDLE = "idle"
    INTERPRETING = "interpreting"
    GATHERING = "gathering"
    STRUCTURING = "structuring"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


_VALID_TRANSITIONS: dict[CommunicationState, frozenset[CommunicationState]] = {
    CommunicationState.IDLE: frozenset({CommunicationState.INTERPRETING, CommunicationState.FAILED}),
    CommunicationState.INTERPRETING: frozenset(
        {CommunicationState.GATHERING, CommunicationState.STRUCTURING, CommunicationState.FAILED}
    ),
    CommunicationState.GATHERING: frozenset({CommunicationState.STRUCTURING, CommunicationState.FAILED}),
    CommunicationState.STRUCTURING: frozenset({CommunicationState.SYNTHESIZING, CommunicationState.FAILED}),
    CommunicationState.SYNTHESIZING: frozenset({CommunicationState.COMPLETED, CommunicationState.FAILED}),
    CommunicationState.COMPLETED: frozenset({CommunicationState.IDLE}),
    CommunicationState.FAILED: frozenset({CommunicationState.IDLE}),
}


class InvalidCommunicationStateTransitionError(AgentError):
    """Raised when a CommunicationState transition is not allowed from the
    current state."""


class CommunicationStateMachine:
    def __init__(self, initial: CommunicationState = CommunicationState.IDLE) -> None:
        self._state = initial

    @property
    def state(self) -> CommunicationState:
        return self._state

    def can_transition(self, target: CommunicationState) -> bool:
        return target in _VALID_TRANSITIONS.get(self._state, frozenset())

    def transition(self, target: CommunicationState) -> None:
        if not self.can_transition(target):
            raise InvalidCommunicationStateTransitionError(f"Cannot transition from {self._state} to {target}")
        self._state = target
