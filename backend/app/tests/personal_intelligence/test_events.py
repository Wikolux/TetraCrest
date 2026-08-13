"""PersonalIntelligenceEvent / PersonalIntelligenceEventPublisher - built
on the shared GenericEvent/EventPublisher base, not a new event mechanism.
"""

import pytest

from app.services.ai.agents.specialists.personal_intelligence.events import (
    PersonalIntelligenceEvent,
    PersonalIntelligenceEventPublisher,
    PersonalIntelligenceEventType,
)
from app.services.ai.shared.events import EventPublisher, GenericEvent


def test_event_type_has_all_eleven_documented_members():
    assert {member.value for member in PersonalIntelligenceEventType} == {
        "request_started",
        "context_retrieved",
        "identity_remembered",
        "goal_remembered",
        "goal_progress_updated",
        "project_remembered",
        "reflection_remembered",
        "preference_remembered",
        "recall_completed",
        "request_completed",
        "request_failed",
    }


def test_event_is_a_generic_event_subclass():
    assert issubclass(PersonalIntelligenceEvent, GenericEvent)


def test_event_publisher_is_a_generic_event_publisher_subclass():
    assert issubclass(PersonalIntelligenceEventPublisher, EventPublisher)


def _event(**overrides):
    defaults = dict(
        event_type=PersonalIntelligenceEventType.GOAL_REMEMBERED,
        execution_id="exec-1",
        correlation_id="corr-1",
        agent_id="personal_intelligence",
    )
    defaults.update(overrides)
    return PersonalIntelligenceEvent(**defaults)


def test_event_is_frozen_and_hashable():
    event = _event()
    hash(event)  # must not raise

    with pytest.raises(AttributeError):
        event.agent_id = "someone-else"


def test_event_carries_execution_and_correlation_identity():
    event = _event(execution_id="exec-42", correlation_id="corr-42")
    assert event.execution_id == "exec-42"
    assert event.correlation_id == "corr-42"


def test_publisher_dispatches_to_every_subscriber_synchronously():
    received_a = []
    received_b = []
    publisher = PersonalIntelligenceEventPublisher()
    publisher.subscribe(received_a.append)
    publisher.subscribe(received_b.append)

    event = _event()
    publisher.publish(event)

    assert received_a == [event]
    assert received_b == [event]


def test_publisher_with_no_subscribers_does_not_raise():
    PersonalIntelligenceEventPublisher().publish(_event())


def test_event_data_defaults_to_an_empty_mapping_and_accepts_extras():
    event = _event(data={"item_count": 3})
    assert event.data["item_count"] == 3
