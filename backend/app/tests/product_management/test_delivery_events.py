"""DeliveryEvent/DeliveryEventPublisher - mirrors test_discovery_events.py's/
test_decision_events.py's own coverage exactly.
"""

from app.services.ai.agents.specialists.product_management.delivery.events import (
    DeliveryEvent,
    DeliveryEventPublisher,
    DeliveryEventType,
)


def _event(event_type=DeliveryEventType.REQUEST_STARTED, execution_id="exec-1"):
    return DeliveryEvent(event_type=event_type, execution_id=execution_id, agent_id="delivery")


def test_event_is_hashable():
    hash(_event())


def test_correlation_id_defaults_to_execution_id():
    event = _event(execution_id="exec-42")
    assert event.correlation_id == "exec-42"


def test_publisher_dispatches_synchronously_in_subscription_order():
    publisher = DeliveryEventPublisher()
    received: list[str] = []
    publisher.subscribe(lambda e: received.append("first"))
    publisher.subscribe(lambda e: received.append("second"))

    publisher.publish(_event())

    assert received == ["first", "second"]


def test_all_event_types_are_distinct():
    values = [member.value for member in DeliveryEventType]
    assert len(values) == len(set(values))


def test_event_carries_data_mapping():
    event = DeliveryEvent(
        event_type=DeliveryEventType.CONFIDENCE_SCORED, execution_id="exec-1", agent_id="delivery", data={"score_percent": 75}
    )
    assert event.data["score_percent"] == 75
