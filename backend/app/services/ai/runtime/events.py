"""Synchronous, in-process event publishing.

RuntimeEventPublisher stores subscribers and dispatches to them
synchronously, in registration order, on the same thread that calls
publish() - no external broker, no queue, no async dispatch. A future
milestone wanting real delivery (webhooks, a message queue, ...) would
build that as a subscriber of this publisher, not replace it.

Built on EventPublisher (app.services.ai.shared.events) rather than hand-
rolling the same subscribe/unsubscribe/publish/subscriber_count shape -
the same base every other XEventPublisher in the platform now uses.
"""

from app.services.ai.runtime.types import RuntimeEvent
from app.services.ai.shared.events import EventPublisher


class RuntimeEventPublisher(EventPublisher[RuntimeEvent]):
    """Stores subscribers and dispatches RuntimeEvents to them synchronously.

    Instance-level, not a global/singleton - one publisher belongs to one
    RuntimeExecutor (or is shared explicitly by whoever constructs one).
    """
