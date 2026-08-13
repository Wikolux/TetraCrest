import pytest

from app.services.ai.agents.executive.state import (
    ExecutiveState,
    ExecutiveStateMachine,
    InvalidExecutiveStateTransitionError,
)
from app.services.ai.agents.types import AgentError


def test_default_initial_state_is_idle():
    assert ExecutiveStateMachine().state == ExecutiveState.IDLE


def test_custom_initial_state():
    assert ExecutiveStateMachine(initial=ExecutiveState.PLANNING).state == ExecutiveState.PLANNING


def test_invalid_transition_error_is_an_agent_error():
    assert issubclass(InvalidExecutiveStateTransitionError, AgentError)


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (ExecutiveState.IDLE, ExecutiveState.PLANNING),
        (ExecutiveState.PLANNING, ExecutiveState.RETRIEVING_MEMORY),
        (ExecutiveState.PLANNING, ExecutiveState.DISPATCHING),
        (ExecutiveState.RETRIEVING_MEMORY, ExecutiveState.DISPATCHING),
        (ExecutiveState.DISPATCHING, ExecutiveState.WAITING),
        (ExecutiveState.WAITING, ExecutiveState.COLLECTING),
        (ExecutiveState.COLLECTING, ExecutiveState.RESPONDING),
        (ExecutiveState.COLLECTING, ExecutiveState.DISPATCHING),
        (ExecutiveState.RESPONDING, ExecutiveState.COMPLETED),
        (ExecutiveState.COMPLETED, ExecutiveState.IDLE),
        (ExecutiveState.FAILED, ExecutiveState.IDLE),
    ],
)
def test_legal_transitions_succeed(start, target):
    machine = ExecutiveStateMachine(initial=start)

    machine.transition(target)

    assert machine.state == target


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (ExecutiveState.IDLE, ExecutiveState.DISPATCHING),
        (ExecutiveState.IDLE, ExecutiveState.COMPLETED),
        (ExecutiveState.PLANNING, ExecutiveState.IDLE),
        (ExecutiveState.COMPLETED, ExecutiveState.RESPONDING),
        (ExecutiveState.WAITING, ExecutiveState.DISPATCHING),
    ],
)
def test_illegal_transitions_raise_and_leave_state_unchanged(start, target):
    machine = ExecutiveStateMachine(initial=start)

    with pytest.raises(InvalidExecutiveStateTransitionError):
        machine.transition(target)

    assert machine.state == start


def test_every_state_can_reach_failed_or_is_terminal_and_recoverable():
    # every non-terminal state can transition to FAILED, and both terminal
    # states (COMPLETED, FAILED) lead back to IDLE, since the Executive
    # handles many requests over its lifetime rather than terminating.
    for state in ExecutiveState:
        if state in (ExecutiveState.COMPLETED, ExecutiveState.FAILED):
            assert ExecutiveStateMachine(initial=state).can_transition(ExecutiveState.IDLE)
        else:
            assert ExecutiveStateMachine(initial=state).can_transition(ExecutiveState.FAILED)
