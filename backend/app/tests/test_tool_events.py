import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.shared.events import EventPublisher, GenericEvent
from app.services.ai.tools.enums import ToolEventType
from app.services.ai.tools.events import ToolEvent, ToolEventPublisher


def test_tool_event_is_built_on_the_generic_event_not_a_parallel_type():
    assert issubclass(ToolEvent, GenericEvent)


def test_publisher_is_built_on_the_generic_publisher():
    assert issubclass(ToolEventPublisher, EventPublisher)


def _event(event_type=ToolEventType.TOOL_STARTED, **overrides):
    defaults = dict(execution_id="exec-1", correlation_id="corr-1", tool_id="fake-tool")
    defaults.update(overrides)
    return ToolEvent(event_type=event_type, **defaults)


def test_construction_requires_execution_id_correlation_id_and_tool_id():
    event = _event(ToolEventType.EXECUTION_STARTED)

    assert event.event_type == ToolEventType.EXECUTION_STARTED
    assert event.execution_id == "exec-1"
    assert event.correlation_id == "corr-1"
    assert event.tool_id == "fake-tool"


def test_agent_id_defaults_to_none():
    assert _event().agent_id is None


def test_agent_id_can_be_set():
    event = _event(agent_id="agent-1")

    assert event.agent_id == "agent-1"


def test_data_defaults_to_empty_read_only_mapping():
    assert isinstance(_event().data, MappingProxyType)


def test_data_cannot_be_mutated():
    event = _event(data={"a": 1})

    with pytest.raises(TypeError):
        event.data["a"] = 2


def test_is_frozen():
    event = _event()

    with pytest.raises(dataclasses.FrozenInstanceError):
        event.tool_id = "changed"


def test_event_is_hashable_despite_holding_a_mappingproxy_data_field():
    event = _event(data={"a": 1})

    assert isinstance(hash(event), int)


def test_publisher_dispatches_synchronously_in_order():
    order = []
    publisher = ToolEventPublisher()
    publisher.subscribe(lambda event: order.append("first"))
    publisher.subscribe(lambda event: order.append("second"))

    publisher.publish(_event())

    assert order == ["first", "second"]


def test_publisher_unsubscribe():
    received = []
    publisher = ToolEventPublisher()
    callback = received.append
    publisher.subscribe(callback)

    publisher.unsubscribe(callback)
    publisher.publish(_event())

    assert received == []
    assert publisher.subscriber_count() == 0


def test_unsubscribe_an_unsubscribed_callback_does_not_raise():
    ToolEventPublisher().unsubscribe(lambda event: None)


def test_two_publishers_never_share_subscribers():
    first, second = ToolEventPublisher(), ToolEventPublisher()
    received = []
    first.subscribe(received.append)

    second.publish(_event())

    assert received == []
