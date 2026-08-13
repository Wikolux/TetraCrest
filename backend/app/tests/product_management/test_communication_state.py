"""CommunicationStateMachine - transition-table coverage, mirroring every
prior milestone's own convention.
"""

import pytest

from app.services.ai.agents.specialists.product_management.stakeholder_communication.state import (
    CommunicationState,
    CommunicationStateMachine,
    InvalidCommunicationStateTransitionError,
)


def test_starts_idle():
    assert CommunicationStateMachine().state == CommunicationState.IDLE


def test_full_happy_path_gathering():
    machine = CommunicationStateMachine()
    machine.transition(CommunicationState.INTERPRETING)
    machine.transition(CommunicationState.GATHERING)
    machine.transition(CommunicationState.STRUCTURING)
    machine.transition(CommunicationState.SYNTHESIZING)
    machine.transition(CommunicationState.COMPLETED)
    machine.transition(CommunicationState.IDLE)
    assert machine.state == CommunicationState.IDLE


def test_interpreting_can_skip_gathering_straight_to_structuring():
    machine = CommunicationStateMachine()
    machine.transition(CommunicationState.INTERPRETING)
    machine.transition(CommunicationState.STRUCTURING)
    assert machine.state == CommunicationState.STRUCTURING


@pytest.mark.parametrize(
    "source",
    [
        CommunicationState.IDLE,
        CommunicationState.INTERPRETING,
        CommunicationState.GATHERING,
        CommunicationState.STRUCTURING,
        CommunicationState.SYNTHESIZING,
    ],
)
def test_every_non_terminal_state_can_fail(source):
    machine = CommunicationStateMachine(initial=source)
    assert machine.can_transition(CommunicationState.FAILED)
    machine.transition(CommunicationState.FAILED)
    assert machine.state == CommunicationState.FAILED


def test_both_terminal_states_return_to_idle():
    completed = CommunicationStateMachine(initial=CommunicationState.COMPLETED)
    completed.transition(CommunicationState.IDLE)
    assert completed.state == CommunicationState.IDLE

    failed = CommunicationStateMachine(initial=CommunicationState.FAILED)
    failed.transition(CommunicationState.IDLE)
    assert failed.state == CommunicationState.IDLE


def test_invalid_transition_raises():
    machine = CommunicationStateMachine()
    with pytest.raises(InvalidCommunicationStateTransitionError):
        machine.transition(CommunicationState.SYNTHESIZING)


def test_gathering_cannot_skip_structuring():
    machine = CommunicationStateMachine(initial=CommunicationState.GATHERING)
    assert not machine.can_transition(CommunicationState.SYNTHESIZING)
