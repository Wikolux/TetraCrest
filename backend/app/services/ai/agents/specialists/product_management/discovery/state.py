"""DiscoveryState - where the Discovery Specialist is in its own cognitive
cycle for one request. Distinct from AgentState and from
ResearchState/PersonalIntelligenceState (each specialist's own domain-
specific cycle) - realizes the exact topology CP-02 Architecture §16
names: interpret what's being asked, gather product/professional/CP-01
context (skippable for lightweight operations), structure the result
through a Professional Standards Framework or evidence discipline,
synthesize via Runtime-backed generation, then finish.

Like ResearchState/PersonalIntelligenceState, FAILED is reachable from
every non-terminal state (defensive completeness, not shown explicitly in
Architecture §16's illustrative diagram but consistent with every other
specialist state machine on the platform), and both terminal states
(COMPLETED, FAILED) lead back to IDLE.
"""

from enum import StrEnum

from app.services.ai.agents.types import AgentError


class DiscoveryState(StrEnum):
    IDLE = "idle"
    INTERPRETING = "interpreting"
    GATHERING = "gathering"
    STRUCTURING = "structuring"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


_VALID_TRANSITIONS: dict[DiscoveryState, frozenset[DiscoveryState]] = {
    DiscoveryState.IDLE: frozenset({DiscoveryState.INTERPRETING, DiscoveryState.FAILED}),
    DiscoveryState.INTERPRETING: frozenset(
        {DiscoveryState.GATHERING, DiscoveryState.STRUCTURING, DiscoveryState.FAILED}
    ),
    DiscoveryState.GATHERING: frozenset({DiscoveryState.STRUCTURING, DiscoveryState.FAILED}),
    DiscoveryState.STRUCTURING: frozenset({DiscoveryState.SYNTHESIZING, DiscoveryState.FAILED}),
    DiscoveryState.SYNTHESIZING: frozenset({DiscoveryState.COMPLETED, DiscoveryState.FAILED}),
    DiscoveryState.COMPLETED: frozenset({DiscoveryState.IDLE}),
    DiscoveryState.FAILED: frozenset({DiscoveryState.IDLE}),
}


class InvalidDiscoveryStateTransitionError(AgentError):
    """Raised when a DiscoveryState transition is not allowed from the
    current state."""


class DiscoveryStateMachine:
    def __init__(self, initial: DiscoveryState = DiscoveryState.IDLE) -> None:
        self._state = initial

    @property
    def state(self) -> DiscoveryState:
        return self._state

    def can_transition(self, target: DiscoveryState) -> bool:
        return target in _VALID_TRANSITIONS.get(self._state, frozenset())

    def transition(self, target: DiscoveryState) -> None:
        if not self.can_transition(target):
            raise InvalidDiscoveryStateTransitionError(f"Cannot transition from {self._state} to {target}")
        self._state = target
