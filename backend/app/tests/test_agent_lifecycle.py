import pytest

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentEventType, AgentState
from app.services.ai.agents.events import AgentEventPublisher
from app.services.ai.agents.lifecycle import AgentLifecycle
from app.services.ai.agents.state import InvalidStateTransitionError
from app.services.ai.agents.types import AgentIdentity
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeResponse


class _FakeAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentIdentity(agent_id="agent-1", name="fake", display_name="Fake Agent"))
        self.initialize_calls = 0
        self.pause_calls = 0
        self.resume_calls = 0
        self.cancel_calls = 0
        self.shutdown_calls = 0

    def initialize(self) -> None:
        self.initialize_calls += 1

    def execute(self, context: AgentContext) -> RuntimeResponse:
        return RuntimeResponse(success=True)

    def pause(self) -> None:
        self.pause_calls += 1

    def resume(self) -> None:
        self.resume_calls += 1

    def cancel(self) -> None:
        self.cancel_calls += 1

    def shutdown(self) -> None:
        self.shutdown_calls += 1

    def health(self) -> bool:
        return True

    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities()

    def permissions(self) -> tuple[str, ...]:
        return ()

    def memory(self):
        return None

    def planner(self):
        return None

    def runtime(self) -> AIRuntime:
        return AIRuntime()


def _lifecycle():
    agent = _FakeAgent()
    events = []
    publisher = AgentEventPublisher()
    publisher.subscribe(events.append)
    return AgentLifecycle(agent, event_publisher=publisher), agent, events


def test_create_emits_created_event_without_changing_state():
    lifecycle, agent, events = _lifecycle()

    lifecycle.create()

    assert agent.state == AgentState.CREATED
    assert [e.event_type for e in events] == [AgentEventType.CREATED]


def test_initialize_transitions_to_ready_and_calls_agent_initialize():
    lifecycle, agent, events = _lifecycle()

    lifecycle.initialize()

    assert agent.state == AgentState.READY
    assert agent.initialize_calls == 1
    assert [e.event_type for e in events] == [AgentEventType.INITIALIZED]


def test_initialize_without_a_context_leaves_the_events_execution_id_none():
    lifecycle, agent, events = _lifecycle()

    lifecycle.initialize()

    assert events[0].execution_id is None


def test_initialize_with_a_context_stamps_the_events_execution_id():
    lifecycle, agent, events = _lifecycle()
    context = AgentContext()

    lifecycle.initialize(context)

    assert events[0].execution_id == context.execution_id


def test_run_delegates_to_an_executor_and_produces_a_result():
    lifecycle, agent, _ = _lifecycle()
    lifecycle.initialize()

    result = lifecycle.run(AgentContext())

    assert result.success is True
    assert agent.state == AgentState.READY


def test_pause_transitions_and_calls_agent_pause():
    lifecycle, agent, events = _lifecycle()
    lifecycle.initialize()
    agent.state_machine.transition(AgentState.RUNNING)  # pause is only valid from RUNNING
    events.clear()

    lifecycle.pause()

    assert agent.state == AgentState.PAUSED
    assert agent.pause_calls == 1
    assert [e.event_type for e in events] == [AgentEventType.PAUSED]


def test_resume_transitions_paused_to_running_and_calls_agent_resume():
    lifecycle, agent, events = _lifecycle()
    lifecycle.initialize()
    agent.state_machine.transition(AgentState.RUNNING)
    lifecycle.pause()
    events.clear()

    lifecycle.resume()

    assert agent.state == AgentState.RUNNING
    assert agent.resume_calls == 1
    assert [e.event_type for e in events] == [AgentEventType.RESUMED]


def test_cancel_transitions_and_calls_agent_cancel():
    lifecycle, agent, events = _lifecycle()
    lifecycle.initialize()
    events.clear()

    lifecycle.cancel()

    assert agent.state == AgentState.CANCELLED
    assert agent.cancel_calls == 1
    assert [e.event_type for e in events] == [AgentEventType.CANCELLED]


def test_shutdown_transitions_and_calls_agent_shutdown():
    lifecycle, agent, events = _lifecycle()
    lifecycle.initialize()
    events.clear()

    lifecycle.shutdown()

    assert agent.state == AgentState.STOPPED
    assert agent.shutdown_calls == 1
    assert [e.event_type for e in events] == [AgentEventType.SHUTDOWN]


def test_dispose_raises_when_agent_is_not_in_a_terminal_state():
    lifecycle, agent, _ = _lifecycle()
    lifecycle.initialize()

    with pytest.raises(InvalidStateTransitionError):
        lifecycle.dispose()


def test_dispose_succeeds_once_stopped():
    lifecycle, agent, _ = _lifecycle()
    lifecycle.initialize()
    lifecycle.shutdown()

    lifecycle.dispose()  # must not raise


def test_pausing_a_non_running_agent_raises_invalid_state_transition():
    lifecycle, agent, _ = _lifecycle()  # still CREATED

    with pytest.raises(InvalidStateTransitionError):
        lifecycle.pause()
