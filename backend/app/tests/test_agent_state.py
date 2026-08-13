import pytest

from app.services.ai.agents.enums import AgentState
from app.services.ai.agents.state import AgentStateMachine, InvalidStateTransitionError
from app.services.ai.agents.types import AgentError


def test_default_initial_state_is_created():
    assert AgentStateMachine().state == AgentState.CREATED


def test_custom_initial_state():
    assert AgentStateMachine(initial=AgentState.READY).state == AgentState.READY


def test_invalid_state_transition_error_is_an_agent_error():
    assert issubclass(InvalidStateTransitionError, AgentError)


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (AgentState.CREATED, AgentState.INITIALIZING),
        (AgentState.INITIALIZING, AgentState.READY),
        (AgentState.READY, AgentState.RUNNING),
        (AgentState.RUNNING, AgentState.WAITING),
        (AgentState.RUNNING, AgentState.PAUSED),
        (AgentState.RUNNING, AgentState.READY),
        (AgentState.WAITING, AgentState.RUNNING),
        (AgentState.PAUSED, AgentState.RUNNING),
        (AgentState.READY, AgentState.STOPPED),
        (AgentState.CANCELLED, AgentState.STOPPED),
        (AgentState.FAILED, AgentState.STOPPED),
    ],
)
def test_legal_transitions_succeed(start, target):
    machine = AgentStateMachine(initial=start)

    machine.transition(target)

    assert machine.state == target


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (AgentState.CREATED, AgentState.RUNNING),
        (AgentState.CREATED, AgentState.READY),
        (AgentState.READY, AgentState.INITIALIZING),
        (AgentState.STOPPED, AgentState.RUNNING),
        (AgentState.STOPPED, AgentState.CREATED),
        (AgentState.PAUSED, AgentState.WAITING),
        (AgentState.CANCELLED, AgentState.RUNNING),
    ],
)
def test_illegal_transitions_raise_and_leave_state_unchanged(start, target):
    machine = AgentStateMachine(initial=start)

    with pytest.raises(InvalidStateTransitionError):
        machine.transition(target)

    assert machine.state == start


def test_can_transition_reflects_transition_without_mutating_state():
    machine = AgentStateMachine(initial=AgentState.READY)

    assert machine.can_transition(AgentState.RUNNING) is True
    assert machine.can_transition(AgentState.INITIALIZING) is False
    assert machine.state == AgentState.READY


def test_stopped_has_no_further_valid_transitions():
    machine = AgentStateMachine(initial=AgentState.STOPPED)

    for target in AgentState:
        assert machine.can_transition(target) is False
