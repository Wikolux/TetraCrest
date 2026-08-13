import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.shared.events import EventPublisher, GenericEvent


def _event(**overrides):
    defaults = dict(event_type="started", execution_id="exec-1", correlation_id="corr-1")
    defaults.update(overrides)
    return GenericEvent(**defaults)


def test_construction():
    event = _event()

    assert event.event_type == "started"
    assert event.execution_id == "exec-1"
    assert event.correlation_id == "corr-1"


def test_data_defaults_to_empty_read_only_mapping():
    assert isinstance(_event().data, MappingProxyType)


def test_data_cannot_be_mutated():
    event = _event(data={"a": 1})

    with pytest.raises(TypeError):
        event.data["a"] = 2


def test_is_frozen():
    event = _event()

    with pytest.raises(dataclasses.FrozenInstanceError):
        event.execution_id = "changed"


def test_event_is_hashable_despite_holding_a_mappingproxy_data_field():
    event = _event(data={"a": 1})

    assert isinstance(hash(event), int)


def test_correlation_id_defaults_to_execution_id_when_omitted():
    event = GenericEvent(event_type="started", execution_id="exec-1")

    assert event.correlation_id == "exec-1"


def test_correlation_id_is_not_overridden_when_explicitly_given():
    event = _event(correlation_id="corr-2")

    assert event.correlation_id == "corr-2"


def test_publisher_starts_with_no_subscribers():
    assert EventPublisher().subscriber_count() == 0


def test_publisher_dispatches_synchronously_in_order():
    order = []
    publisher = EventPublisher()
    publisher.subscribe(lambda event: order.append("first"))
    publisher.subscribe(lambda event: order.append("second"))

    publisher.publish(_event())

    assert order == ["first", "second"]


def test_publisher_unsubscribe():
    received = []
    publisher = EventPublisher()
    callback = received.append
    publisher.subscribe(callback)

    publisher.unsubscribe(callback)
    publisher.publish(_event())

    assert received == []


def test_unsubscribe_an_unsubscribed_callback_does_not_raise():
    EventPublisher().unsubscribe(lambda event: None)


def test_two_publishers_never_share_subscribers():
    first, second = EventPublisher(), EventPublisher()
    received = []
    first.subscribe(received.append)

    second.publish(_event())

    assert received == []
