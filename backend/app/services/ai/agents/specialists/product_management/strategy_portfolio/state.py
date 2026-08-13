"""StrategyState - identical topology to DiscoveryState/DecisionState/
DeliveryState (Milestones 3-5), which itself realizes CP-02 Architecture
§16's shared, cross-specialist state topology.
"""

from enum import StrEnum

from app.services.ai.agents.types import AgentError


class StrategyState(StrEnum):
    IDLE = "idle"
    INTERPRETING = "interpreting"
    GATHERING = "gathering"
    STRUCTURING = "structuring"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


_VALID_TRANSITIONS: dict[StrategyState, frozenset[StrategyState]] = {
    StrategyState.IDLE: frozenset({StrategyState.INTERPRETING, StrategyState.FAILED}),
    StrategyState.INTERPRETING: frozenset(
        {StrategyState.GATHERING, StrategyState.STRUCTURING, StrategyState.FAILED}
    ),
    StrategyState.GATHERING: frozenset({StrategyState.STRUCTURING, StrategyState.FAILED}),
    StrategyState.STRUCTURING: frozenset({StrategyState.SYNTHESIZING, StrategyState.FAILED}),
    StrategyState.SYNTHESIZING: frozenset({StrategyState.COMPLETED, StrategyState.FAILED}),
    StrategyState.COMPLETED: frozenset({StrategyState.IDLE}),
    StrategyState.FAILED: frozenset({StrategyState.IDLE}),
}


class InvalidStrategyStateTransitionError(AgentError):
    """Raised when a StrategyState transition is not allowed from the
    current state."""


class StrategyStateMachine:
    def __init__(self, initial: StrategyState = StrategyState.IDLE) -> None:
        self._state = initial

    @property
    def state(self) -> StrategyState:
        return self._state

    def can_transition(self, target: StrategyState) -> bool:
        return target in _VALID_TRANSITIONS.get(self._state, frozenset())

    def transition(self, target: StrategyState) -> None:
        if not self.can_transition(target):
            raise InvalidStrategyStateTransitionError(f"Cannot transition from {self._state} to {target}")
        self._state = target
