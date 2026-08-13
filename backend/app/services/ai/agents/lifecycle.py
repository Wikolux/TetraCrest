"""AgentLifecycle - manages an agent's coarse lifecycle: creation through
disposal. Distinct from AgentExecutor, which supervises a single
execute() cycle; run() here delegates to an AgentExecutor for that part
rather than duplicating its state/event handling.

Every transition emits a lifecycle event, except create() (the state
machine already starts at CREATED the moment an agent is constructed, so
create() only confirms/announces that) and dispose() (no DISPOSED event
exists in AgentEventType - STOPPED/CANCELLED/FAILED are already terminal
states, so dispose() only asserts terminality and does final cleanup).

Every transition method accepts an optional `context: AgentContext` so a
caller that has one (e.g. an orchestrator driving this agent as part of a
larger execution tree) can correlate the emitted event with it via
execution_id; when no context is given (the common case - most lifecycle
transitions happen outside of any one execution), the event's
execution_id is simply None.
"""

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentEventType, AgentState
from app.services.ai.agents.events import AgentEvent, AgentEventPublisher
from app.services.ai.agents.execution import AgentExecutor
from app.services.ai.agents.state import InvalidStateTransitionError
from app.services.ai.agents.types import AgentExecutionResult


class AgentLifecycle:
    def __init__(
        self,
        agent: BaseAgent,
        event_publisher: AgentEventPublisher | None = None,
        executor: AgentExecutor | None = None,
    ) -> None:
        self.agent = agent
        self.event_publisher = event_publisher or AgentEventPublisher()
        self.executor = executor or AgentExecutor(event_publisher=self.event_publisher)

    def create(self, context: AgentContext | None = None) -> None:
        self._emit(AgentEventType.CREATED, context)

    def initialize(self, context: AgentContext | None = None) -> None:
        self.agent.state_machine.transition(AgentState.INITIALIZING)
        self.agent.initialize()
        self.agent.state_machine.transition(AgentState.READY)
        self._emit(AgentEventType.INITIALIZED, context)

    def run(self, context: AgentContext) -> AgentExecutionResult:
        return self.executor.execute(self.agent, context)

    def pause(self, context: AgentContext | None = None) -> None:
        self.agent.state_machine.transition(AgentState.PAUSED)
        self.agent.pause()
        self._emit(AgentEventType.PAUSED, context)

    def resume(self, context: AgentContext | None = None) -> None:
        self.agent.state_machine.transition(AgentState.RUNNING)
        self.agent.resume()
        self._emit(AgentEventType.RESUMED, context)

    def cancel(self, context: AgentContext | None = None) -> None:
        self.agent.state_machine.transition(AgentState.CANCELLED)
        self.agent.cancel()
        self._emit(AgentEventType.CANCELLED, context)

    def shutdown(self, context: AgentContext | None = None) -> None:
        self.agent.state_machine.transition(AgentState.STOPPED)
        self.agent.shutdown()
        self._emit(AgentEventType.SHUTDOWN, context)

    def dispose(self) -> None:
        if self.agent.state_machine.state not in (AgentState.STOPPED, AgentState.CANCELLED, AgentState.FAILED):
            raise InvalidStateTransitionError(
                f"Cannot dispose an agent in state {self.agent.state_machine.state}"
            )

    def _emit(self, event_type: AgentEventType, context: AgentContext | None, **data) -> None:
        self.event_publisher.publish(
            AgentEvent(
                event_type=event_type,
                agent_id=self.agent.identity.agent_id,
                execution_id=context.execution_id if context is not None else None,
                data=data,
            )
        )
