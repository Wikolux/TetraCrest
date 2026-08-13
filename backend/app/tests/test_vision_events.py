import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.shared.events import GenericEvent
from app.services.ai.vision.events import VisionEvent, VisionEventPublisher, VisionEventType


def _event(event_type=VisionEventType.VISION_STARTED, **overrides):
    defaults = dict(execution_id="exec-1", correlation_id="corr-1")
    defaults.update(overrides)
    return VisionEvent(event_type=event_type, **defaults)


def test_every_documented_event_type_exists():
    assert {member.value for member in VisionEventType} == {
        "vision_started",
        "image_analyzed",
        "document_analyzed",
        "text_extracted",
        "table_extracted",
        "objects_detected",
        "vision_completed",
        "vision_failed",
    }


def test_vision_event_is_built_on_the_generic_event_not_a_parallel_type():
    assert issubclass(VisionEvent, GenericEvent)


def test_construction_carries_execution_id_correlation_id_and_timestamp():
    event = _event(VisionEventType.IMAGE_ANALYZED)

    assert event.event_type == VisionEventType.IMAGE_ANALYZED
    assert event.execution_id == "exec-1"
    assert event.correlation_id == "corr-1"
    assert isinstance(event.timestamp, float)


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


def test_publisher_is_built_on_the_generic_publisher():
    from app.services.ai.shared.events import EventPublisher

    assert issubclass(VisionEventPublisher, EventPublisher)


def test_publisher_dispatches_synchronously_in_order():
    order = []
    publisher = VisionEventPublisher()
    publisher.subscribe(lambda event: order.append("first"))
    publisher.subscribe(lambda event: order.append("second"))

    publisher.publish(_event())

    assert order == ["first", "second"]


def test_publisher_unsubscribe():
    received = []
    publisher = VisionEventPublisher()
    callback = received.append
    publisher.subscribe(callback)

    publisher.unsubscribe(callback)
    publisher.publish(_event())

    assert received == []


def test_two_publishers_never_share_subscribers():
    first, second = VisionEventPublisher(), VisionEventPublisher()
    received = []
    first.subscribe(received.append)

    second.publish(_event())

    assert received == []
