"""DiscoveryEvent/DiscoveryEventPublisher - mirrors test_research_events.py's
own coverage: hashability (the __hash__ = hash_event restatement every
GenericEvent subclass must make), and synchronous, subscription-order
dispatch.
"""

from app.services.ai.agents.specialists.product_management.discovery.events import (
    DiscoveryEvent,
    DiscoveryEventPublisher,
    DiscoveryEventType,
)


def _event(event_type=DiscoveryEventType.REQUEST_STARTED, execution_id="exec-1"):
    return DiscoveryEvent(event_type=event_type, execution_id=execution_id, agent_id="discovery")


def test_event_is_hashable():
    event = _event()
    hash(event)  # must not raise


def test_event_carries_data_mapping():
    event = DiscoveryEvent(
        event_type=DiscoveryEventType.FINDING_RECORDED,
        execution_id="exec-1",
        agent_id="discovery",
        data={"memory_type": "product_discovery_finding"},
    )
    assert event.data["memory_type"] == "product_discovery_finding"


def test_correlation_id_defaults_to_execution_id():
    event = _event(execution_id="exec-42")
    assert event.correlation_id == "exec-42"


def test_publisher_dispatches_synchronously_in_subscription_order():
    publisher = DiscoveryEventPublisher()
    received: list[str] = []
    publisher.subscribe(lambda e: received.append("first"))
    publisher.subscribe(lambda e: received.append("second"))

    publisher.publish(_event())

    assert received == ["first", "second"]


def test_publisher_with_no_subscribers_does_not_raise():
    publisher = DiscoveryEventPublisher()
    publisher.publish(_event())  # must not raise


def test_all_event_types_are_distinct():
    values = [member.value for member in DiscoveryEventType]
    assert len(values) == len(set(values))
