import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.agents.executive.events import ExecutiveEvent, ExecutiveEventPublisher, ExecutiveEventType
from app.services.ai.shared.events import EventPublisher, GenericEvent


def _event(event_type=ExecutiveEventType.PLAN_CREATED):
    return ExecutiveEvent(event_type=event_type, execution_id="exec-1", correlation_id="corr-1")


def test_executive_event_is_built_on_the_generic_event_not_a_parallel_type():
    assert issubclass(ExecutiveEvent, GenericEvent)


def test_publisher_is_built_on_the_generic_publisher():
    assert issubclass(ExecutiveEventPublisher, EventPublisher)


def test_event_is_hashable_despite_holding_a_mappingproxy_data_field():
    event = ExecutiveEvent(
        event_type=ExecutiveEventType.PLAN_CREATED, execution_id="e", correlation_id="c", data={"a": 1}
    )

    assert isinstance(hash(event), int)


def test_event_construction_requires_execution_and_correlation_id():
    event = _event(ExecutiveEventType.TASK_CREATED)

    assert event.event_type == ExecutiveEventType.TASK_CREATED
    assert event.execution_id == "exec-1"
    assert event.correlation_id == "corr-1"


def test_event_data_defaults_to_empty_read_only_mapping():
    assert isinstance(_event().data, MappingProxyType)


def test_event_data_cannot_be_mutated():
    event = ExecutiveEvent(
        event_type=ExecutiveEventType.PLAN_CREATED, execution_id="e", correlation_id="c", data={"a": 1}
    )

    with pytest.raises(TypeError):
        event.data["a"] = 2


def test_event_is_frozen():
    event = _event()

    with pytest.raises(dataclasses.FrozenInstanceError):
        event.execution_id = "changed"


def test_every_documented_event_type_exists():
    assert {member.value for member in ExecutiveEventType} == {
        "plan_created",
        "task_created",
        "task_assigned",
        "task_completed",
        "task_failed",
        "delegation_started",
        "delegation_completed",
        "response_generated",
    }


def test_publisher_dispatches_synchronously_in_order():
    order = []
    publisher = ExecutiveEventPublisher()
    publisher.subscribe(lambda event: order.append("first"))
    publisher.subscribe(lambda event: order.append("second"))

    publisher.publish(_event())

    assert order == ["first", "second"]


def test_publisher_unsubscribe():
    received = []
    publisher = ExecutiveEventPublisher()
    callback = received.append
    publisher.subscribe(callback)

    publisher.unsubscribe(callback)
    publisher.publish(_event())

    assert received == []
    assert publisher.subscriber_count() == 0
