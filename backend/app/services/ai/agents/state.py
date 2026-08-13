"""The agent state machine - formal, validated transitions between
AgentState values. An illegal transition raises InvalidStateTransitionError
rather than silently applying.

WAITING and PAUSED are deliberately distinct: WAITING is the agent
blocking itself on something (a tool call, a sub-agent, I/O) as part of
its own execution, while PAUSED is an external caller suspending it via
BaseAgent.pause() - the same distinction an OS draws between a process
blocking on I/O versus being stopped by a signal.
"""

from app.services.ai.agents.enums import AgentState
from app.services.ai.agents.types import AgentError

_VALID_TRANSITIONS: dict[AgentState, frozenset[AgentState]] = {
    AgentState.CREATED: frozenset({AgentState.INITIALIZING, AgentState.CANCELLED, AgentState.FAILED}),
    AgentState.INITIALIZING: frozenset({AgentState.READY, AgentState.FAILED, AgentState.CANCELLED}),
    AgentState.READY: frozenset(
        {AgentState.RUNNING, AgentState.STOPPED, AgentState.CANCELLED, AgentState.FAILED}
    ),
    AgentState.RUNNING: frozenset(
        {
            AgentState.WAITING,
            AgentState.PAUSED,
            AgentState.READY,
            AgentState.CANCELLED,
            AgentState.FAILED,
            AgentState.STOPPED,
        }
    ),
    AgentState.WAITING: frozenset({AgentState.RUNNING, AgentState.CANCELLED, AgentState.FAILED}),
    AgentState.PAUSED: frozenset({AgentState.RUNNING, AgentState.CANCELLED, AgentState.STOPPED}),
    AgentState.CANCELLED: frozenset({AgentState.STOPPED}),
    AgentState.FAILED: frozenset({AgentState.STOPPED}),
    AgentState.STOPPED: frozenset(),
}


class InvalidStateTransitionError(AgentError):
    """Raised when a transition is not allowed from the current state."""


class AgentStateMachine:
    """Owns one agent's current AgentState and validates every transition
    against _VALID_TRANSITIONS.

    Instance-level: one machine belongs to one agent instance. Mutable by
    design (state changes constantly during execution) - contrast with
    every other Agent Framework value object, which is frozen.
    """

    def __init__(self, initial: AgentState = AgentState.CREATED) -> None:
        self._state = initial

    @property
    def state(self) -> AgentState:
        return self._state

    def can_transition(self, target: AgentState) -> bool:
        return target in _VALID_TRANSITIONS.get(self._state, frozenset())

    def transition(self, target: AgentState) -> None:
        if not self.can_transition(target):
            raise InvalidStateTransitionError(f"Cannot transition from {self._state} to {target}")
        self._state = target
