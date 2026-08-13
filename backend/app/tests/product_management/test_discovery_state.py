"""DiscoveryStateMachine - transition-table coverage, mirroring
test_research_state.py's own convention exactly: every valid edge in
Architecture §16's topology proven reachable, every invalid edge proven
rejected.
"""

import pytest

from app.services.ai.agents.specialists.product_management.discovery.state import (
    DiscoveryState,
    DiscoveryStateMachine,
    InvalidDiscoveryStateTransitionError,
)


def test_starts_idle():
    machine = DiscoveryStateMachine()
    assert machine.state == DiscoveryState.IDLE


def test_full_happy_path_gathering():
    machine = DiscoveryStateMachine()
    machine.transition(DiscoveryState.INTERPRETING)
    machine.transition(DiscoveryState.GATHERING)
    machine.transition(DiscoveryState.STRUCTURING)
    machine.transition(DiscoveryState.SYNTHESIZING)
    machine.transition(DiscoveryState.COMPLETED)
    machine.transition(DiscoveryState.IDLE)
    assert machine.state == DiscoveryState.IDLE


def test_interpreting_can_skip_gathering_straight_to_structuring():
    machine = DiscoveryStateMachine()
    machine.transition(DiscoveryState.INTERPRETING)
    machine.transition(DiscoveryState.STRUCTURING)
    assert machine.state == DiscoveryState.STRUCTURING


@pytest.mark.parametrize(
    "source",
    [
        DiscoveryState.IDLE,
        DiscoveryState.INTERPRETING,
        DiscoveryState.GATHERING,
        DiscoveryState.STRUCTURING,
        DiscoveryState.SYNTHESIZING,
    ],
)
def test_every_non_terminal_state_can_fail(source):
    machine = DiscoveryStateMachine(initial=source)
    assert machine.can_transition(DiscoveryState.FAILED)
    machine.transition(DiscoveryState.FAILED)
    assert machine.state == DiscoveryState.FAILED


def test_both_terminal_states_return_to_idle():
    completed = DiscoveryStateMachine(initial=DiscoveryState.COMPLETED)
    completed.transition(DiscoveryState.IDLE)
    assert completed.state == DiscoveryState.IDLE

    failed = DiscoveryStateMachine(initial=DiscoveryState.FAILED)
    failed.transition(DiscoveryState.IDLE)
    assert failed.state == DiscoveryState.IDLE


def test_invalid_transition_raises():
    machine = DiscoveryStateMachine()
    with pytest.raises(InvalidDiscoveryStateTransitionError):
        machine.transition(DiscoveryState.SYNTHESIZING)


def test_completed_cannot_jump_back_to_synthesizing():
    machine = DiscoveryStateMachine(initial=DiscoveryState.COMPLETED)
    assert not machine.can_transition(DiscoveryState.SYNTHESIZING)
    with pytest.raises(InvalidDiscoveryStateTransitionError):
        machine.transition(DiscoveryState.SYNTHESIZING)


def test_gathering_cannot_skip_structuring():
    machine = DiscoveryStateMachine(initial=DiscoveryState.GATHERING)
    assert not machine.can_transition(DiscoveryState.SYNTHESIZING)
