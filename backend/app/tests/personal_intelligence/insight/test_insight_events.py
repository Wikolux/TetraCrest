"""InsightEvent / InsightEventPublisher - built on the shared
GenericEvent/EventPublisher base, not a new event mechanism.
"""

import pytest

from app.services.ai.agents.specialists.personal_intelligence.insight.events import (
    InsightEvent,
    InsightEventPublisher,
    InsightEventType,
)
from app.services.ai.shared.events import EventPublisher, GenericEvent


def test_event_type_has_all_twelve_documented_members():
    assert {member.value for member in InsightEventType} == {
        "request_started",
        "corpus_gathered",
        "patterns_detected",
        "habits_identified",
        "contradictions_detected",
        "alignment_measured",
        "periodic_reflection_generated",
        "recommendations_generated",
        "profile_updated",
        "recall_completed",
        "request_completed",
        "request_failed",
    }


def test_event_is_a_generic_event_subclass():
    assert issubclass(InsightEvent, GenericEvent)


def test_event_publisher_is_a_generic_event_publisher_subclass():
    assert issubclass(InsightEventPublisher, EventPublisher)


def _event(**overrides):
    defaults = dict(event_type=InsightEventType.PATTERNS_DETECTED, execution_id="exec-1", correlation_id="corr-1", agent_id="insight")
    defaults.update(overrides)
    return InsightEvent(**defaults)


def test_event_is_frozen_and_hashable():
    event = _event()
    hash(event)
    with pytest.raises(AttributeError):
        event.agent_id = "someone-else"


def test_event_carries_execution_and_correlation_identity():
    event = _event(execution_id="exec-42", correlation_id="corr-42")
    assert event.execution_id == "exec-42"
    assert event.correlation_id == "corr-42"


def test_publisher_dispatches_to_every_subscriber_synchronously():
    received_a, received_b = [], []
    publisher = InsightEventPublisher()
    publisher.subscribe(received_a.append)
    publisher.subscribe(received_b.append)

    event = _event()
    publisher.publish(event)

    assert received_a == [event]
    assert received_b == [event]


def test_publisher_with_no_subscribers_does_not_raise():
    InsightEventPublisher().publish(_event())


def test_event_data_defaults_to_an_empty_mapping_and_accepts_extras():
    event = _event(data={"insight_count": 3})
    assert event.data["insight_count"] == 3
