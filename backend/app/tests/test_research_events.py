import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.agents.specialists.research.events import (
    ResearchEvent,
    ResearchEventPublisher,
    ResearchEventType,
)
from app.services.ai.shared.events import EventPublisher, GenericEvent


def test_research_event_is_built_on_the_generic_event_not_a_parallel_type():
    assert issubclass(ResearchEvent, GenericEvent)


def test_publisher_is_built_on_the_generic_publisher():
    assert issubclass(ResearchEventPublisher, EventPublisher)


def _event(event_type=ResearchEventType.RESEARCH_STARTED, **overrides):
    defaults = dict(execution_id="exec-1", correlation_id="corr-1", agent_id="research")
    defaults.update(overrides)
    return ResearchEvent(event_type=event_type, **defaults)


def test_every_documented_event_type_exists():
    assert {member.value for member in ResearchEventType} == {
        "research_started",
        "plan_created",
        "memory_retrieved",
        "tools_completed",
        "synthesis_completed",
        "report_generated",
        "research_completed",
        "research_failed",
    }


def test_construction_requires_execution_id_correlation_id_and_agent_id():
    event = _event(ResearchEventType.PLAN_CREATED)

    assert event.event_type == ResearchEventType.PLAN_CREATED
    assert event.execution_id == "exec-1"
    assert event.correlation_id == "corr-1"
    assert event.agent_id == "research"


def test_data_defaults_to_empty_read_only_mapping():
    assert isinstance(_event().data, MappingProxyType)


def test_data_cannot_be_mutated():
    event = _event(data={"a": 1})

    with pytest.raises(TypeError):
        event.data["a"] = 2


def test_is_frozen():
    event = _event()

    with pytest.raises(dataclasses.FrozenInstanceError):
        event.agent_id = "changed"


def test_event_is_hashable_despite_holding_a_mappingproxy_data_field():
    event = _event(data={"a": 1})

    assert isinstance(hash(event), int)


def test_publisher_dispatches_synchronously_in_order():
    order = []
    publisher = ResearchEventPublisher()
    publisher.subscribe(lambda event: order.append("first"))
    publisher.subscribe(lambda event: order.append("second"))

    publisher.publish(_event())

    assert order == ["first", "second"]


def test_publisher_unsubscribe():
    received = []
    publisher = ResearchEventPublisher()
    callback = received.append
    publisher.subscribe(callback)

    publisher.unsubscribe(callback)
    publisher.publish(_event())

    assert received == []
    assert publisher.subscriber_count() == 0


def test_two_publishers_never_share_subscribers():
    first, second = ResearchEventPublisher(), ResearchEventPublisher()
    received = []
    first.subscribe(received.append)

    second.publish(_event())

    assert received == []
