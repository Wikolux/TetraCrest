import pytest

from app.services.ai.agents.specialists.research.state import (
    InvalidResearchStateTransitionError,
    ResearchState,
    ResearchStateMachine,
)
from app.services.ai.agents.types import AgentError


def test_default_initial_state_is_idle():
    assert ResearchStateMachine().state == ResearchState.IDLE


def test_custom_initial_state():
    assert ResearchStateMachine(initial=ResearchState.PLANNING).state == ResearchState.PLANNING


def test_invalid_transition_error_is_an_agent_error():
    assert issubclass(InvalidResearchStateTransitionError, AgentError)


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (ResearchState.IDLE, ResearchState.PLANNING),
        (ResearchState.PLANNING, ResearchState.RETRIEVING),
        (ResearchState.RETRIEVING, ResearchState.ANALYZING),
        (ResearchState.ANALYZING, ResearchState.SYNTHESIZING),
        (ResearchState.SYNTHESIZING, ResearchState.GENERATING),
        (ResearchState.GENERATING, ResearchState.COMPLETED),
        (ResearchState.COMPLETED, ResearchState.IDLE),
        (ResearchState.FAILED, ResearchState.IDLE),
    ],
)
def test_legal_transitions_succeed(start, target):
    machine = ResearchStateMachine(initial=start)

    machine.transition(target)

    assert machine.state == target


@pytest.mark.parametrize("state", list(ResearchState))
def test_every_non_terminal_state_can_reach_failed_and_terminal_states_reach_idle(state):
    machine = ResearchStateMachine(initial=state)

    if state in (ResearchState.COMPLETED, ResearchState.FAILED):
        assert machine.can_transition(ResearchState.IDLE)
    else:
        assert machine.can_transition(ResearchState.FAILED)


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (ResearchState.IDLE, ResearchState.RETRIEVING),
        (ResearchState.PLANNING, ResearchState.IDLE),
        (ResearchState.COMPLETED, ResearchState.GENERATING),
    ],
)
def test_illegal_transitions_raise_and_leave_state_unchanged(start, target):
    machine = ResearchStateMachine(initial=start)

    with pytest.raises(InvalidResearchStateTransitionError):
        machine.transition(target)

    assert machine.state == start
