"""StrategyStateMachine - transition-table coverage, mirroring
test_discovery_state.py's/test_decision_state.py's/test_delivery_state.py's
own convention.
"""

import pytest

from app.services.ai.agents.specialists.product_management.strategy_portfolio.state import (
    InvalidStrategyStateTransitionError,
    StrategyState,
    StrategyStateMachine,
)


def test_starts_idle():
    assert StrategyStateMachine().state == StrategyState.IDLE


def test_full_happy_path_gathering():
    machine = StrategyStateMachine()
    machine.transition(StrategyState.INTERPRETING)
    machine.transition(StrategyState.GATHERING)
    machine.transition(StrategyState.STRUCTURING)
    machine.transition(StrategyState.SYNTHESIZING)
    machine.transition(StrategyState.COMPLETED)
    machine.transition(StrategyState.IDLE)
    assert machine.state == StrategyState.IDLE


def test_interpreting_can_skip_gathering_straight_to_structuring():
    machine = StrategyStateMachine()
    machine.transition(StrategyState.INTERPRETING)
    machine.transition(StrategyState.STRUCTURING)
    assert machine.state == StrategyState.STRUCTURING


@pytest.mark.parametrize(
    "source",
    [
        StrategyState.IDLE,
        StrategyState.INTERPRETING,
        StrategyState.GATHERING,
        StrategyState.STRUCTURING,
        StrategyState.SYNTHESIZING,
    ],
)
def test_every_non_terminal_state_can_fail(source):
    machine = StrategyStateMachine(initial=source)
    assert machine.can_transition(StrategyState.FAILED)
    machine.transition(StrategyState.FAILED)
    assert machine.state == StrategyState.FAILED


def test_both_terminal_states_return_to_idle():
    completed = StrategyStateMachine(initial=StrategyState.COMPLETED)
    completed.transition(StrategyState.IDLE)
    assert completed.state == StrategyState.IDLE

    failed = StrategyStateMachine(initial=StrategyState.FAILED)
    failed.transition(StrategyState.IDLE)
    assert failed.state == StrategyState.IDLE


def test_invalid_transition_raises():
    machine = StrategyStateMachine()
    with pytest.raises(InvalidStrategyStateTransitionError):
        machine.transition(StrategyState.SYNTHESIZING)


def test_gathering_cannot_skip_structuring():
    machine = StrategyStateMachine(initial=StrategyState.GATHERING)
    assert not machine.can_transition(StrategyState.SYNTHESIZING)
