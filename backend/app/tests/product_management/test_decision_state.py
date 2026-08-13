"""DecisionStateMachine - transition-table coverage, mirroring
test_discovery_state.py's own convention exactly."""

import pytest

from app.services.ai.agents.specialists.product_management.product_decision.state import (
    DecisionState,
    DecisionStateMachine,
    InvalidDecisionStateTransitionError,
)


def test_starts_idle():
    assert DecisionStateMachine().state == DecisionState.IDLE


def test_full_happy_path_gathering():
    machine = DecisionStateMachine()
    machine.transition(DecisionState.INTERPRETING)
    machine.transition(DecisionState.GATHERING)
    machine.transition(DecisionState.STRUCTURING)
    machine.transition(DecisionState.SYNTHESIZING)
    machine.transition(DecisionState.COMPLETED)
    machine.transition(DecisionState.IDLE)
    assert machine.state == DecisionState.IDLE


def test_interpreting_can_skip_gathering_straight_to_structuring():
    machine = DecisionStateMachine()
    machine.transition(DecisionState.INTERPRETING)
    machine.transition(DecisionState.STRUCTURING)
    assert machine.state == DecisionState.STRUCTURING


@pytest.mark.parametrize(
    "source",
    [
        DecisionState.IDLE,
        DecisionState.INTERPRETING,
        DecisionState.GATHERING,
        DecisionState.STRUCTURING,
        DecisionState.SYNTHESIZING,
    ],
)
def test_every_non_terminal_state_can_fail(source):
    machine = DecisionStateMachine(initial=source)
    assert machine.can_transition(DecisionState.FAILED)
    machine.transition(DecisionState.FAILED)
    assert machine.state == DecisionState.FAILED


def test_both_terminal_states_return_to_idle():
    completed = DecisionStateMachine(initial=DecisionState.COMPLETED)
    completed.transition(DecisionState.IDLE)
    assert completed.state == DecisionState.IDLE

    failed = DecisionStateMachine(initial=DecisionState.FAILED)
    failed.transition(DecisionState.IDLE)
    assert failed.state == DecisionState.IDLE


def test_invalid_transition_raises():
    machine = DecisionStateMachine()
    with pytest.raises(InvalidDecisionStateTransitionError):
        machine.transition(DecisionState.SYNTHESIZING)


def test_gathering_cannot_skip_structuring():
    machine = DecisionStateMachine(initial=DecisionState.GATHERING)
    assert not machine.can_transition(DecisionState.SYNTHESIZING)
