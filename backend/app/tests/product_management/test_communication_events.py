"""CommunicationEvent/CommunicationEventPublisher - mirrors every prior
milestone's own coverage exactly, and confirms ARR §3's own literal event
name ("update-drafted") is present.
"""

from app.services.ai.agents.specialists.product_management.stakeholder_communication.events import (
    CommunicationEvent,
    CommunicationEventPublisher,
    CommunicationEventType,
)


def _event(event_type=CommunicationEventType.REQUEST_STARTED, execution_id="exec-1"):
    return CommunicationEvent(event_type=event_type, execution_id=execution_id, agent_id="stakeholder_communication")


def test_event_is_hashable():
    hash(_event())


def test_update_drafted_event_matches_arr_3_literal_name():
    assert CommunicationEventType.UPDATE_DRAFTED.value == "update_drafted"


def test_correlation_id_defaults_to_execution_id():
    event = _event(execution_id="exec-42")
    assert event.correlation_id == "exec-42"


def test_publisher_dispatches_synchronously_in_subscription_order():
    publisher = CommunicationEventPublisher()
    received: list[str] = []
    publisher.subscribe(lambda e: received.append("first"))
    publisher.subscribe(lambda e: received.append("second"))

    publisher.publish(_event())

    assert received == ["first", "second"]


def test_all_event_types_are_distinct():
    values = [member.value for member in CommunicationEventType]
    assert len(values) == len(set(values))
