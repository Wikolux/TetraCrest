from app.services.ai.runtime.events import RuntimeEventPublisher
from app.services.ai.runtime.types import EventType, RuntimeEvent
from app.services.ai.shared.events import EventPublisher, GenericEvent


def _event(event_type=EventType.STARTED):
    return RuntimeEvent(event_type=event_type, execution_id="exec-1")


def test_runtime_event_is_built_on_the_generic_event_not_a_parallel_type():
    assert issubclass(RuntimeEvent, GenericEvent)


def test_publisher_is_built_on_the_generic_publisher():
    assert issubclass(RuntimeEventPublisher, EventPublisher)


def test_event_is_hashable_despite_holding_a_mappingproxy_data_field():
    event = RuntimeEvent(event_type=EventType.STARTED, execution_id="exec-1", data={"a": 1})

    assert isinstance(hash(event), int)


def test_correlation_id_defaults_to_execution_id():
    event = _event()

    assert event.correlation_id == "exec-1"


def test_publisher_starts_with_no_subscribers():
    assert RuntimeEventPublisher().subscriber_count() == 0


def test_subscribe_adds_a_subscriber():
    publisher = RuntimeEventPublisher()

    publisher.subscribe(lambda event: None)

    assert publisher.subscriber_count() == 1


def test_publish_dispatches_synchronously_to_every_subscriber():
    received_a, received_b = [], []
    publisher = RuntimeEventPublisher()
    publisher.subscribe(received_a.append)
    publisher.subscribe(received_b.append)

    event = _event()
    publisher.publish(event)

    assert received_a == [event]
    assert received_b == [event]


def test_publish_dispatches_in_subscription_order():
    order = []
    publisher = RuntimeEventPublisher()
    publisher.subscribe(lambda event: order.append("first"))
    publisher.subscribe(lambda event: order.append("second"))

    publisher.publish(_event())

    assert order == ["first", "second"]


def test_publish_with_no_subscribers_does_not_raise():
    RuntimeEventPublisher().publish(_event())  # must not raise


def test_unsubscribe_removes_a_subscriber():
    received = []
    publisher = RuntimeEventPublisher()
    callback = received.append
    publisher.subscribe(callback)

    publisher.unsubscribe(callback)
    publisher.publish(_event())

    assert received == []
    assert publisher.subscriber_count() == 0


def test_unsubscribe_an_unsubscribed_callback_does_not_raise():
    RuntimeEventPublisher().unsubscribe(lambda event: None)  # must not raise


def test_two_publishers_never_share_subscribers():
    first, second = RuntimeEventPublisher(), RuntimeEventPublisher()
    received = []
    first.subscribe(received.append)

    second.publish(_event())

    assert received == []
