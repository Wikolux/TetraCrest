"""DeliveryStateMachine - transition-table coverage, mirroring
test_discovery_state.py's/test_decision_state.py's own convention.
"""

import pytest

from app.services.ai.agents.specialists.product_management.delivery.state import (
    DeliveryState,
    DeliveryStateMachine,
    InvalidDeliveryStateTransitionError,
)


def test_starts_idle():
    assert DeliveryStateMachine().state == DeliveryState.IDLE


def test_full_happy_path_gathering():
    machine = DeliveryStateMachine()
    machine.transition(DeliveryState.INTERPRETING)
    machine.transition(DeliveryState.GATHERING)
    machine.transition(DeliveryState.STRUCTURING)
    machine.transition(DeliveryState.SYNTHESIZING)
    machine.transition(DeliveryState.COMPLETED)
    machine.transition(DeliveryState.IDLE)
    assert machine.state == DeliveryState.IDLE


def test_interpreting_can_skip_gathering_straight_to_structuring():
    machine = DeliveryStateMachine()
    machine.transition(DeliveryState.INTERPRETING)
    machine.transition(DeliveryState.STRUCTURING)
    assert machine.state == DeliveryState.STRUCTURING


@pytest.mark.parametrize(
    "source",
    [
        DeliveryState.IDLE,
        DeliveryState.INTERPRETING,
        DeliveryState.GATHERING,
        DeliveryState.STRUCTURING,
        DeliveryState.SYNTHESIZING,
    ],
)
def test_every_non_terminal_state_can_fail(source):
    machine = DeliveryStateMachine(initial=source)
    assert machine.can_transition(DeliveryState.FAILED)
    machine.transition(DeliveryState.FAILED)
    assert machine.state == DeliveryState.FAILED


def test_both_terminal_states_return_to_idle():
    completed = DeliveryStateMachine(initial=DeliveryState.COMPLETED)
    completed.transition(DeliveryState.IDLE)
    assert completed.state == DeliveryState.IDLE

    failed = DeliveryStateMachine(initial=DeliveryState.FAILED)
    failed.transition(DeliveryState.IDLE)
    assert failed.state == DeliveryState.IDLE


def test_invalid_transition_raises():
    machine = DeliveryStateMachine()
    with pytest.raises(InvalidDeliveryStateTransitionError):
        machine.transition(DeliveryState.SYNTHESIZING)


def test_gathering_cannot_skip_structuring():
    machine = DeliveryStateMachine(initial=DeliveryState.GATHERING)
    assert not machine.can_transition(DeliveryState.SYNTHESIZING)
