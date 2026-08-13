"""DecisionState - where the Product Decision Specialist is in its own
cognitive cycle for one request. Identical topology to Discovery's
DiscoveryState (Milestone 3), which itself realizes CP-02 Architecture
§16's shared, cross-specialist state topology - not a coincidence, the
explicit design intent ("every CP-02 specialist reuses the identical
state-machine pattern"). GATHERING retrieves precedent (prior decisions,
Discovery evidence); STRUCTURING is where a framework is selected and
applied - the step genuinely new relative to CP-01's own topology, per
Architecture §16's own note.
"""

from enum import StrEnum

from app.services.ai.agents.types import AgentError


class DecisionState(StrEnum):
    IDLE = "idle"
    INTERPRETING = "interpreting"
    GATHERING = "gathering"
    STRUCTURING = "structuring"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


_VALID_TRANSITIONS: dict[DecisionState, frozenset[DecisionState]] = {
    DecisionState.IDLE: frozenset({DecisionState.INTERPRETING, DecisionState.FAILED}),
    DecisionState.INTERPRETING: frozenset(
        {DecisionState.GATHERING, DecisionState.STRUCTURING, DecisionState.FAILED}
    ),
    DecisionState.GATHERING: frozenset({DecisionState.STRUCTURING, DecisionState.FAILED}),
    DecisionState.STRUCTURING: frozenset({DecisionState.SYNTHESIZING, DecisionState.FAILED}),
    DecisionState.SYNTHESIZING: frozenset({DecisionState.COMPLETED, DecisionState.FAILED}),
    DecisionState.COMPLETED: frozenset({DecisionState.IDLE}),
    DecisionState.FAILED: frozenset({DecisionState.IDLE}),
}


class InvalidDecisionStateTransitionError(AgentError):
    """Raised when a DecisionState transition is not allowed from the
    current state."""


class DecisionStateMachine:
    def __init__(self, initial: DecisionState = DecisionState.IDLE) -> None:
        self._state = initial

    @property
    def state(self) -> DecisionState:
        return self._state

    def can_transition(self, target: DecisionState) -> bool:
        return target in _VALID_TRANSITIONS.get(self._state, frozenset())

    def transition(self, target: DecisionState) -> None:
        if not self.can_transition(target):
            raise InvalidDecisionStateTransitionError(f"Cannot transition from {self._state} to {target}")
        self._state = target
