"""StrategyEvent/StrategyEventPublisher - mirrors test_discovery_events.py's/
test_decision_events.py's/test_delivery_events.py's own coverage exactly.
"""

from app.services.ai.agents.specialists.product_management.strategy_portfolio.events import (
    StrategyEvent,
    StrategyEventPublisher,
    StrategyEventType,
)


def _event(event_type=StrategyEventType.REQUEST_STARTED, execution_id="exec-1"):
    return StrategyEvent(event_type=event_type, execution_id=execution_id, agent_id="strategy_portfolio")


def test_event_is_hashable():
    hash(_event())


def test_correlation_id_defaults_to_execution_id():
    event = _event(execution_id="exec-42")
    assert event.correlation_id == "exec-42"


def test_publisher_dispatches_synchronously_in_subscription_order():
    publisher = StrategyEventPublisher()
    received: list[str] = []
    publisher.subscribe(lambda e: received.append("first"))
    publisher.subscribe(lambda e: received.append("second"))

    publisher.publish(_event())

    assert received == ["first", "second"]


def test_all_event_types_are_distinct():
    values = [member.value for member in StrategyEventType]
    assert len(values) == len(set(values))


def test_roadmap_and_cross_product_conflict_categories_are_named_per_architecture_15():
    values = {member.value for member in StrategyEventType}
    assert "roadmap_revised" in values
    assert "cross_product_conflict_surfaced" in values
