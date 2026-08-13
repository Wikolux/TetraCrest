"""ResearchState - where the Research Agent is in its own cognitive
execution cycle for one request. Distinct from AgentState (the agent's
OS-process-like lifecycle) and from ExecutiveState (the Executive's own
plan -> dispatch -> collect cycle) - this is the Research Agent's own
domain-specific cycle: plan -> retrieve -> analyze -> synthesize ->
generate -> respond.

Like ExecutiveState, both terminal states (COMPLETED, FAILED) lead back
to IDLE: the Research Agent is long-lived and handles many requests over
its lifetime.
"""

from enum import StrEnum

from app.services.ai.agents.types import AgentError


class ResearchState(StrEnum):
    IDLE = "idle"
    PLANNING = "planning"
    RETRIEVING = "retrieving"
    ANALYZING = "analyzing"
    SYNTHESIZING = "synthesizing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


_VALID_TRANSITIONS: dict[ResearchState, frozenset[ResearchState]] = {
    ResearchState.IDLE: frozenset({ResearchState.PLANNING, ResearchState.FAILED}),
    ResearchState.PLANNING: frozenset({ResearchState.RETRIEVING, ResearchState.FAILED}),
    ResearchState.RETRIEVING: frozenset({ResearchState.ANALYZING, ResearchState.FAILED}),
    ResearchState.ANALYZING: frozenset({ResearchState.SYNTHESIZING, ResearchState.FAILED}),
    ResearchState.SYNTHESIZING: frozenset({ResearchState.GENERATING, ResearchState.FAILED}),
    ResearchState.GENERATING: frozenset({ResearchState.COMPLETED, ResearchState.FAILED}),
    ResearchState.COMPLETED: frozenset({ResearchState.IDLE}),
    ResearchState.FAILED: frozenset({ResearchState.IDLE}),
}


class InvalidResearchStateTransitionError(AgentError):
    """Raised when a ResearchState transition is not allowed from the
    current state."""


class ResearchStateMachine:
    def __init__(self, initial: ResearchState = ResearchState.IDLE) -> None:
        self._state = initial

    @property
    def state(self) -> ResearchState:
        return self._state

    def can_transition(self, target: ResearchState) -> bool:
        return target in _VALID_TRANSITIONS.get(self._state, frozenset())

    def transition(self, target: ResearchState) -> None:
        if not self.can_transition(target):
            raise InvalidResearchStateTransitionError(f"Cannot transition from {self._state} to {target}")
        self._state = target
