"""InsightStateMachine - mirrors PersonalIntelligenceStateMachine's exact
transition-table testing approach, narrowed to Insight's own five active
states (IDLE/INTERPRETING/GATHERING/ANALYZING/COMPLETED/FAILED).
"""

import pytest

from app.services.ai.agents.specialists.personal_intelligence.insight.state import (
    InsightState,
    InsightStateMachine,
    InvalidInsightStateTransitionError,
)
from app.services.ai.agents.types import AgentError


def test_starts_idle_by_default():
    assert InsightStateMachine().state == InsightState.IDLE


def test_can_be_constructed_with_a_custom_initial_state():
    machine = InsightStateMachine(initial=InsightState.ANALYZING)
    assert machine.state == InsightState.ANALYZING


def test_the_analysis_happy_path_is_fully_traversable():
    machine = InsightStateMachine()
    for target in (InsightState.INTERPRETING, InsightState.GATHERING, InsightState.ANALYZING, InsightState.COMPLETED, InsightState.IDLE):
        machine.transition(target)
        assert machine.state == target


def test_interpreting_can_skip_gathering_and_go_straight_to_analyzing():
    # RECALL_INSIGHTS retrieves+synthesizes without a bulk-gather phase.
    machine = InsightStateMachine()
    machine.transition(InsightState.INTERPRETING)
    machine.transition(InsightState.ANALYZING)
    assert machine.state == InsightState.ANALYZING


@pytest.mark.parametrize("source", [InsightState.IDLE, InsightState.INTERPRETING, InsightState.GATHERING, InsightState.ANALYZING])
def test_every_non_terminal_state_can_transition_to_failed(source):
    machine = InsightStateMachine(initial=source)
    assert machine.can_transition(InsightState.FAILED)
    machine.transition(InsightState.FAILED)
    assert machine.state == InsightState.FAILED


def test_both_completed_and_failed_lead_back_to_idle():
    for terminal in (InsightState.COMPLETED, InsightState.FAILED):
        machine = InsightStateMachine(initial=terminal)
        machine.transition(InsightState.IDLE)
        assert machine.state == InsightState.IDLE


def test_an_invalid_transition_raises_and_does_not_change_state():
    machine = InsightStateMachine()
    with pytest.raises(InvalidInsightStateTransitionError):
        machine.transition(InsightState.COMPLETED)
    assert machine.state == InsightState.IDLE


def test_can_transition_returns_false_without_raising_for_an_invalid_target():
    assert InsightStateMachine().can_transition(InsightState.COMPLETED) is False


def test_invalid_transition_error_is_an_agent_error():
    assert issubclass(InvalidInsightStateTransitionError, AgentError)


def test_state_enum_has_exactly_six_documented_states():
    assert {member.value for member in InsightState} == {"idle", "interpreting", "gathering", "analyzing", "completed", "failed"}
