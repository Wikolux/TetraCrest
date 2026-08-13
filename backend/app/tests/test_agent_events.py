import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.agents.enums import AgentEventType
from app.services.ai.agents.events import AgentEvent, AgentEventPublisher
from app.services.ai.shared.events import EventPublisher, GenericEvent


def _event(event_type=AgentEventType.CREATED):
    return AgentEvent(event_type=event_type, agent_id="agent-1")


# --- AgentEvent -----------------------------------------------------------------


def test_agent_event_is_built_on_the_generic_event_not_a_parallel_type():
    assert issubclass(AgentEvent, GenericEvent)


def test_publisher_is_built_on_the_generic_publisher():
    assert issubclass(AgentEventPublisher, EventPublisher)


def test_agent_event_is_hashable_despite_holding_a_mappingproxy_data_field():
    event = AgentEvent(event_type=AgentEventType.CREATED, agent_id="agent-1", data={"a": 1})

    assert isinstance(hash(event), int)


def test_agent_event_is_hashable_even_when_execution_id_is_none():
    assert isinstance(hash(_event()), int)


def test_agent_event_construction():
    event = _event(AgentEventType.STARTED)

    assert event.event_type == AgentEventType.STARTED
    assert event.agent_id == "agent-1"


def test_agent_event_data_defaults_to_empty_read_only_mapping():
    event = _event()

    assert isinstance(event.data, MappingProxyType)
    assert dict(event.data) == {}


def test_agent_event_data_cannot_be_mutated():
    event = AgentEvent(event_type=AgentEventType.CREATED, agent_id="agent-1", data={"a": 1})

    with pytest.raises(TypeError):
        event.data["a"] = 2


def test_agent_event_is_frozen():
    event = _event()

    with pytest.raises(dataclasses.FrozenInstanceError):
        event.agent_id = "changed"


def test_agent_event_execution_id_defaults_to_none():
    event = _event()

    assert event.execution_id is None


def test_agent_event_execution_id_can_be_set():
    event = AgentEvent(event_type=AgentEventType.STARTED, agent_id="agent-1", execution_id="exec-1")

    assert event.execution_id == "exec-1"


def test_agent_event_execution_id_and_agent_id_are_distinct_identifiers():
    # execution_id (which execution) and agent_id (who emitted it) must
    # never collapse into the same field
    event = AgentEvent(event_type=AgentEventType.STARTED, agent_id="agent-1", execution_id="exec-1")

    assert event.agent_id != event.execution_id


# --- AgentEventPublisher ----------------------------------------------------------


def test_publisher_starts_with_no_subscribers():
    assert AgentEventPublisher().subscriber_count() == 0


def test_publish_dispatches_synchronously_to_every_subscriber_in_order():
    order = []
    publisher = AgentEventPublisher()
    publisher.subscribe(lambda event: order.append("first"))
    publisher.subscribe(lambda event: order.append("second"))

    publisher.publish(_event())

    assert order == ["first", "second"]


def test_publish_with_no_subscribers_does_not_raise():
    AgentEventPublisher().publish(_event())  # must not raise


def test_unsubscribe_removes_a_subscriber():
    received = []
    publisher = AgentEventPublisher()
    callback = received.append
    publisher.subscribe(callback)

    publisher.unsubscribe(callback)
    publisher.publish(_event())

    assert received == []


def test_unsubscribe_an_unsubscribed_callback_does_not_raise():
    AgentEventPublisher().unsubscribe(lambda event: None)  # must not raise


def test_two_publishers_never_share_subscribers():
    first, second = AgentEventPublisher(), AgentEventPublisher()
    received = []
    first.subscribe(received.append)

    second.publish(_event())

    assert received == []
