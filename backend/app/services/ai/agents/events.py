"""Agent lifecycle events - identical in philosophy to the Runtime's
events (app.services.ai.runtime.events): one typed event shape carrying an
event-type discriminator, plus a publisher that stores subscribers and
dispatches to them synchronously. No event bus, no external broker.

Built on GenericEvent/EventPublisher (app.services.ai.shared.events) rather
than hand-rolling the same shape/dispatch logic - the same base every other
XEvent/XEventPublisher pair in the platform now uses.
"""

from dataclasses import dataclass

from app.services.ai.agents.enums import AgentEventType
from app.services.ai.shared.events import EventPublisher, GenericEvent, hash_event


@dataclass(frozen=True, kw_only=True)
class AgentEvent(GenericEvent):
    """One point-in-time occurrence in an agent's lifecycle.

    agent_id (who emitted this) and execution_id (which execution it
    belongs to, from SharedExecutionContext via AgentContext) are
    deliberately both present and distinct, not duplicates of each other.
    execution_id is optional - overriding GenericEvent's normally-required
    execution_id - since AgentExecutor's STARTED/COMPLETED/FAILED events
    always carry one (a real AgentContext is always in scope there), but
    coarse lifecycle events (CREATED/INITIALIZED/PAUSED/...) can happen
    outside of any one execution, so forcing a value there would mean
    fabricating one that doesn't mean anything.
    """

    event_type: AgentEventType
    execution_id: str | None = None
    agent_id: str

    __hash__ = hash_event


class AgentEventPublisher(EventPublisher[AgentEvent]):
    """Stores subscribers and dispatches AgentEvents to them synchronously,
    in subscription order, on the caller's own thread.

    Instance-level, not a global/singleton - one publisher belongs to one
    AgentExecutor/AgentLifecycle (or is shared explicitly by whoever
    constructs one).
    """
