"""PersonalIntelligenceState - where the Personal Intelligence specialist
is in its own cognitive cycle for one request. Distinct from AgentState
(the agent's OS-process-like lifecycle) and from ResearchState/
ExecutiveState (each specialist's own domain-specific cycle) - mirrors
ResearchState's exact shape and reasoning (see
app.services.ai.agents.specialists.research.state), narrowed to Personal
Intelligence's simpler, more uniform operations: interpret what's being
asked, retrieve relevant context, process (write or synthesize a
response), then finish.

Like ResearchState/ExecutiveState, both terminal states (COMPLETED,
FAILED) lead back to IDLE - this specialist is long-lived and handles
many requests over its lifetime.
"""

from enum import StrEnum

from app.services.ai.agents.types import AgentError


class PersonalIntelligenceState(StrEnum):
    IDLE = "idle"
    INTERPRETING = "interpreting"
    RETRIEVING = "retrieving"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


_VALID_TRANSITIONS: dict[PersonalIntelligenceState, frozenset[PersonalIntelligenceState]] = {
    PersonalIntelligenceState.IDLE: frozenset(
        {PersonalIntelligenceState.INTERPRETING, PersonalIntelligenceState.FAILED}
    ),
    PersonalIntelligenceState.INTERPRETING: frozenset(
        {PersonalIntelligenceState.RETRIEVING, PersonalIntelligenceState.PROCESSING, PersonalIntelligenceState.FAILED}
    ),
    PersonalIntelligenceState.RETRIEVING: frozenset(
        {PersonalIntelligenceState.PROCESSING, PersonalIntelligenceState.FAILED}
    ),
    PersonalIntelligenceState.PROCESSING: frozenset(
        {PersonalIntelligenceState.COMPLETED, PersonalIntelligenceState.FAILED}
    ),
    PersonalIntelligenceState.COMPLETED: frozenset({PersonalIntelligenceState.IDLE}),
    PersonalIntelligenceState.FAILED: frozenset({PersonalIntelligenceState.IDLE}),
}


class InvalidPersonalIntelligenceStateTransitionError(AgentError):
    """Raised when a PersonalIntelligenceState transition is not allowed
    from the current state."""


class PersonalIntelligenceStateMachine:
    def __init__(self, initial: PersonalIntelligenceState = PersonalIntelligenceState.IDLE) -> None:
        self._state = initial

    @property
    def state(self) -> PersonalIntelligenceState:
        return self._state

    def can_transition(self, target: PersonalIntelligenceState) -> bool:
        return target in _VALID_TRANSITIONS.get(self._state, frozenset())

    def transition(self, target: PersonalIntelligenceState) -> None:
        if not self.can_transition(target):
            raise InvalidPersonalIntelligenceStateTransitionError(
                f"Cannot transition from {self._state} to {target}"
            )
        self._state = target
