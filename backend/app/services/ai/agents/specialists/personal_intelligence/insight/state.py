"""InsightState - where the Insight Engine specialist is in its own
cognitive cycle for one request. Mirrors PersonalIntelligenceState's/
ResearchState's exact shape and reasoning, narrowed to insight
generation's own phases: interpret what's being asked, gather the memory
corpus to analyze (or recall previously generated insights), analyze it,
then finish. Distinct from AgentState (the agent's OS-process-like
lifecycle).

Like every other specialist state machine in this platform, both terminal
states (COMPLETED, FAILED) lead back to IDLE.
"""

from enum import StrEnum

from app.services.ai.agents.types import AgentError


class InsightState(StrEnum):
    IDLE = "idle"
    INTERPRETING = "interpreting"
    GATHERING = "gathering"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


_VALID_TRANSITIONS: dict[InsightState, frozenset[InsightState]] = {
    InsightState.IDLE: frozenset({InsightState.INTERPRETING, InsightState.FAILED}),
    InsightState.INTERPRETING: frozenset({InsightState.GATHERING, InsightState.ANALYZING, InsightState.FAILED}),
    InsightState.GATHERING: frozenset({InsightState.ANALYZING, InsightState.FAILED}),
    InsightState.ANALYZING: frozenset({InsightState.COMPLETED, InsightState.FAILED}),
    InsightState.COMPLETED: frozenset({InsightState.IDLE}),
    InsightState.FAILED: frozenset({InsightState.IDLE}),
}


class InvalidInsightStateTransitionError(AgentError):
    """Raised when an InsightState transition is not allowed from the
    current state."""


class InsightStateMachine:
    def __init__(self, initial: InsightState = InsightState.IDLE) -> None:
        self._state = initial

    @property
    def state(self) -> InsightState:
        return self._state

    def can_transition(self, target: InsightState) -> bool:
        return target in _VALID_TRANSITIONS.get(self._state, frozenset())

    def transition(self, target: InsightState) -> None:
        if not self.can_transition(target):
            raise InvalidInsightStateTransitionError(f"Cannot transition from {self._state} to {target}")
        self._state = target
