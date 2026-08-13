"""ExecutiveState - where the Executive is in its cognitive execution
cycle for one request. Distinct from AgentState (app.services.ai.agents.state):
AgentState models the agent's own OS-process-like lifecycle (created,
running, stopped, ...), which every agent has regardless of what it does;
ExecutiveState models the specific plan -> retrieve -> dispatch -> collect
-> respond cycle that only the Executive (and future orchestrator agents)
goes through.

Unlike AgentState, COMPLETED and FAILED both lead back to IDLE: the
Executive is a long-lived agent handling many requests over its lifetime,
so finishing one request's cycle should make it ready for the next, not
terminate it. AgentState's own STOPPED remains the true "this agent is
done forever" state, set by BaseAgent.shutdown() - a completely separate
concern from ExecutiveState.
"""

from enum import StrEnum

from app.services.ai.agents.types import AgentError


class ExecutiveState(StrEnum):
    IDLE = "idle"
    PLANNING = "planning"
    RETRIEVING_MEMORY = "retrieving_memory"
    DISPATCHING = "dispatching"
    WAITING = "waiting"
    COLLECTING = "collecting"
    RESPONDING = "responding"
    COMPLETED = "completed"
    FAILED = "failed"


_VALID_TRANSITIONS: dict[ExecutiveState, frozenset[ExecutiveState]] = {
    ExecutiveState.IDLE: frozenset({ExecutiveState.PLANNING, ExecutiveState.FAILED}),
    ExecutiveState.PLANNING: frozenset(
        {ExecutiveState.RETRIEVING_MEMORY, ExecutiveState.DISPATCHING, ExecutiveState.FAILED}
    ),
    ExecutiveState.RETRIEVING_MEMORY: frozenset({ExecutiveState.DISPATCHING, ExecutiveState.FAILED}),
    ExecutiveState.DISPATCHING: frozenset({ExecutiveState.WAITING, ExecutiveState.FAILED}),
    ExecutiveState.WAITING: frozenset({ExecutiveState.COLLECTING, ExecutiveState.FAILED}),
    ExecutiveState.COLLECTING: frozenset(
        {ExecutiveState.RESPONDING, ExecutiveState.DISPATCHING, ExecutiveState.FAILED}
    ),
    ExecutiveState.RESPONDING: frozenset({ExecutiveState.COMPLETED, ExecutiveState.FAILED}),
    ExecutiveState.COMPLETED: frozenset({ExecutiveState.IDLE}),
    ExecutiveState.FAILED: frozenset({ExecutiveState.IDLE}),
}


class InvalidExecutiveStateTransitionError(AgentError):
    """Raised when an ExecutiveState transition is not allowed from the
    current state. A sibling of (not related by inheritance to)
    InvalidStateTransitionError - kept separate since the two state
    machines model different concerns and should never be confused for
    one another when caught."""


class ExecutiveStateMachine:
    def __init__(self, initial: ExecutiveState = ExecutiveState.IDLE) -> None:
        self._state = initial

    @property
    def state(self) -> ExecutiveState:
        return self._state

    def can_transition(self, target: ExecutiveState) -> bool:
        return target in _VALID_TRANSITIONS.get(self._state, frozenset())

    def transition(self, target: ExecutiveState) -> None:
        if not self.can_transition(target):
            raise InvalidExecutiveStateTransitionError(f"Cannot transition from {self._state} to {target}")
        self._state = target
