"""PersonalIntelligenceStateMachine - mirrors ResearchStateMachine's exact
shape and transition-table testing approach.
"""

import pytest

from app.services.ai.agents.specialists.personal_intelligence.state import (
    InvalidPersonalIntelligenceStateTransitionError,
    PersonalIntelligenceState,
    PersonalIntelligenceStateMachine,
)
from app.services.ai.agents.types import AgentError


def test_starts_idle_by_default():
    assert PersonalIntelligenceStateMachine().state == PersonalIntelligenceState.IDLE


def test_can_be_constructed_with_a_custom_initial_state():
    machine = PersonalIntelligenceStateMachine(initial=PersonalIntelligenceState.PROCESSING)
    assert machine.state == PersonalIntelligenceState.PROCESSING


def test_the_documented_happy_path_is_fully_traversable():
    machine = PersonalIntelligenceStateMachine()
    for target in (
        PersonalIntelligenceState.INTERPRETING,
        PersonalIntelligenceState.RETRIEVING,
        PersonalIntelligenceState.PROCESSING,
        PersonalIntelligenceState.COMPLETED,
        PersonalIntelligenceState.IDLE,
    ):
        machine.transition(target)
        assert machine.state == target


def test_interpreting_can_skip_retrieving_and_go_straight_to_processing():
    # write-only operations (remember_*) never retrieve context first.
    machine = PersonalIntelligenceStateMachine()
    machine.transition(PersonalIntelligenceState.INTERPRETING)
    machine.transition(PersonalIntelligenceState.PROCESSING)
    assert machine.state == PersonalIntelligenceState.PROCESSING


@pytest.mark.parametrize(
    "source",
    [
        PersonalIntelligenceState.IDLE,
        PersonalIntelligenceState.INTERPRETING,
        PersonalIntelligenceState.RETRIEVING,
        PersonalIntelligenceState.PROCESSING,
    ],
)
def test_every_non_terminal_state_can_transition_to_failed(source):
    machine = PersonalIntelligenceStateMachine(initial=source)
    assert machine.can_transition(PersonalIntelligenceState.FAILED)
    machine.transition(PersonalIntelligenceState.FAILED)
    assert machine.state == PersonalIntelligenceState.FAILED


def test_both_completed_and_failed_lead_back_to_idle():
    for terminal in (PersonalIntelligenceState.COMPLETED, PersonalIntelligenceState.FAILED):
        machine = PersonalIntelligenceStateMachine(initial=terminal)
        machine.transition(PersonalIntelligenceState.IDLE)
        assert machine.state == PersonalIntelligenceState.IDLE


def test_an_invalid_transition_raises_and_does_not_change_state():
    machine = PersonalIntelligenceStateMachine()  # IDLE
    with pytest.raises(InvalidPersonalIntelligenceStateTransitionError):
        machine.transition(PersonalIntelligenceState.COMPLETED)
    assert machine.state == PersonalIntelligenceState.IDLE


def test_can_transition_returns_false_without_raising_for_an_invalid_target():
    machine = PersonalIntelligenceStateMachine()
    assert machine.can_transition(PersonalIntelligenceState.COMPLETED) is False


def test_invalid_transition_error_is_an_agent_error():
    assert issubclass(InvalidPersonalIntelligenceStateTransitionError, AgentError)


def test_state_enum_has_exactly_six_documented_states():
    assert {member.value for member in PersonalIntelligenceState} == {
        "idle",
        "interpreting",
        "retrieving",
        "processing",
        "completed",
        "failed",
    }
