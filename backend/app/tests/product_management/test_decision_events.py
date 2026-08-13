"""DecisionEvent/DecisionEventPublisher - mirrors test_discovery_events.py's
own coverage exactly, and confirms this milestone's six explicitly-named
lifecycle events are present."""

from app.services.ai.agents.specialists.product_management.product_decision.events import (
    DecisionEvent,
    DecisionEventPublisher,
    DecisionEventType,
)


def _event(event_type=DecisionEventType.REQUEST_STARTED, execution_id="exec-1"):
    return DecisionEvent(event_type=event_type, execution_id=execution_id, agent_id="product_decision")


def test_event_is_hashable():
    hash(_event())


def test_required_lifecycle_events_are_present():
    required = {
        "request_started",
        "framework_selected",
        "decision_generated",
        "decision_stored",
        "request_completed",
        "request_failed",
    }
    values = {member.value for member in DecisionEventType}
    assert required.issubset(values)


def test_correlation_id_defaults_to_execution_id():
    event = _event(execution_id="exec-42")
    assert event.correlation_id == "exec-42"


def test_publisher_dispatches_synchronously_in_subscription_order():
    publisher = DecisionEventPublisher()
    received: list[str] = []
    publisher.subscribe(lambda e: received.append("first"))
    publisher.subscribe(lambda e: received.append("second"))

    publisher.publish(_event())

    assert received == ["first", "second"]


def test_all_event_types_are_distinct():
    values = [member.value for member in DecisionEventType]
    assert len(values) == len(set(values))
