import pytest

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentEventType, AgentState
from app.services.ai.agents.events import AgentEventPublisher
from app.services.ai.agents.execution import AgentExecutor
from app.services.ai.agents.planner import AgentPlanner
from app.services.ai.agents.policies import PermissionPolicy
from app.services.ai.agents.state import AgentStateMachine
from app.services.ai.agents.types import AgentIdentity, AgentPermissionError
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeResponse
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.shared.response import UsageDetails


class _FakeAgent(BaseAgent):
    def __init__(self, identity=None, *, response=None, raises=None, granted_permissions=()):
        super().__init__(identity or _identity(), state_machine=AgentStateMachine(initial=AgentState.READY))
        self._response = response or RuntimeResponse(success=True, provider=ProviderName.OPENAI)
        self._raises = raises
        self._granted_permissions = granted_permissions
        self.executed_with = None

    def initialize(self) -> None:
        return None

    def execute(self, context: AgentContext) -> RuntimeResponse:
        self.executed_with = context
        if self._raises is not None:
            raise self._raises
        return self._response

    def pause(self) -> None:
        return None

    def resume(self) -> None:
        return None

    def cancel(self) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def health(self) -> bool:
        return True

    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities()

    def permissions(self) -> tuple[str, ...]:
        return self._granted_permissions

    def memory(self):
        return None

    def planner(self):
        return None

    def runtime(self) -> AIRuntime:
        return AIRuntime()


class _RecordingPlanner(AgentPlanner):
    def __init__(self):
        self.plan_calls = []

    def plan(self, context):
        self.plan_calls.append(context)
        return ["step-1"]

    def replan(self, context, previous_plan):
        return previous_plan

    def evaluate(self, context, plan):
        return True

    def next_step(self, context, plan):
        return plan[0]


def _identity(**overrides):
    defaults = dict(agent_id="agent-1", name="fake", display_name="Fake Agent")
    defaults.update(overrides)
    return AgentIdentity(**defaults)


def _event_types(result):
    return [event.event_type for event in result.events]


# --- successful execution ------------------------------------------------------------


def test_successful_execution_returns_a_successful_result():
    agent = _FakeAgent()
    executor = AgentExecutor()

    result = executor.execute(agent, AgentContext())

    assert result.success is True
    assert result.state == AgentState.READY
    assert result.agent_id == "agent-1"
    assert result.response.success is True
    assert result.error is None


def test_successful_execution_transitions_ready_to_running_to_ready():
    agent = _FakeAgent()
    executor = AgentExecutor()

    executor.execute(agent, AgentContext())

    assert agent.state == AgentState.READY


def test_successful_execution_emits_started_then_completed():
    agent = _FakeAgent()
    executor = AgentExecutor()

    result = executor.execute(agent, AgentContext())

    assert _event_types(result) == [AgentEventType.STARTED, AgentEventType.COMPLETED]


def test_events_carry_the_contexts_execution_id():
    agent = _FakeAgent()
    executor = AgentExecutor()
    context = AgentContext()

    result = executor.execute(agent, context)

    assert all(event.execution_id == context.execution_id for event in result.events)


def test_events_from_two_different_contexts_carry_different_execution_ids():
    agent = _FakeAgent()
    executor = AgentExecutor()

    first = executor.execute(agent, AgentContext())
    second = executor.execute(agent, AgentContext())

    assert first.events[0].execution_id != second.events[0].execution_id


def test_events_are_published_to_subscribers():
    received = []
    publisher = AgentEventPublisher()
    publisher.subscribe(received.append)
    agent = _FakeAgent()
    executor = AgentExecutor(event_publisher=publisher)

    executor.execute(agent, AgentContext())

    assert [event.event_type for event in received] == [AgentEventType.STARTED, AgentEventType.COMPLETED]


def test_context_is_passed_through_to_agent_execute():
    agent = _FakeAgent()
    executor = AgentExecutor()
    context = AgentContext(organization_id=42)

    executor.execute(agent, context)

    assert agent.executed_with is context


def test_metrics_are_populated_from_the_runtime_response():
    usage = UsageDetails(prompt_tokens=5, completion_tokens=7, total_tokens=12)
    response = RuntimeResponse(
        success=True,
        provider=ProviderName.OPENAI,
        latency_ms=42.0,
        usage=usage,
        conversation_response=None,
    )
    agent = _FakeAgent(response=response)
    executor = AgentExecutor()

    result = executor.execute(agent, AgentContext())

    assert result.metrics is not None
    assert result.metrics.latency_ms == 42.0
    assert result.metrics.token_usage.total_tokens == 12
    assert result.metrics.duration_ms >= 0


# --- execution identity (M16.6) -----------------------------------------------------------


def test_result_carries_identity_fields_copied_from_the_context_not_from_events():
    agent = _FakeAgent()
    executor = AgentExecutor()
    context = AgentContext()

    result = executor.execute(agent, context)

    assert result.execution_id == context.execution_id
    assert result.correlation_id == context.correlation_id
    assert result.parent_execution_id == context.parent_execution_id
    assert result.causation_id == context.causation_id


def test_result_identity_matches_event_identity_exactly():
    agent = _FakeAgent()
    executor = AgentExecutor()

    result = executor.execute(agent, AgentContext())

    event_execution_ids = {event.execution_id for event in result.events}
    assert event_execution_ids == {result.execution_id}


def test_metrics_execution_id_matches_the_results_execution_id():
    agent = _FakeAgent()
    executor = AgentExecutor()

    result = executor.execute(agent, AgentContext())

    assert result.metrics.execution_id == result.execution_id


def test_a_child_context_preserves_correlation_id_in_the_result():
    parent_shared = SharedExecutionContext(organization_id=1)
    child_context = AgentContext(shared=parent_shared.child(), agent_id="agent-1")
    agent = _FakeAgent()
    executor = AgentExecutor()

    result = executor.execute(agent, child_context)

    assert result.correlation_id == parent_shared.correlation_id
    assert result.parent_execution_id == parent_shared.execution_id
    assert result.execution_id != parent_shared.execution_id


def test_failed_execution_still_carries_identity_fields():
    agent = _FakeAgent(raises=ValueError("boom"))
    executor = AgentExecutor()
    context = AgentContext()

    result = executor.execute(agent, context)

    assert result.success is False
    assert result.execution_id == context.execution_id
    assert result.correlation_id == context.correlation_id


# --- planner invocation ------------------------------------------------------------------


def test_planner_is_invoked_when_present():
    planner = _RecordingPlanner()

    class _PlannedAgent(_FakeAgent):
        def planner(self):
            return planner

    agent = _PlannedAgent()
    context = AgentContext()

    AgentExecutor().execute(agent, context)

    assert planner.plan_calls == [context]


def test_no_planner_is_fine():
    agent = _FakeAgent()  # planner() returns None
    executor = AgentExecutor()

    result = executor.execute(agent, AgentContext())

    assert result.success is True


# --- failure handling -----------------------------------------------------------------


def test_agent_execute_raising_produces_a_failed_result_not_a_raised_exception():
    agent = _FakeAgent(raises=ValueError("agent exploded"))
    executor = AgentExecutor()

    result = executor.execute(agent, AgentContext())  # must not raise

    assert result.success is False
    assert result.state == AgentState.FAILED
    assert result.error == "agent exploded"
    assert result.response is None


def test_failure_transitions_running_to_failed():
    agent = _FakeAgent(raises=ValueError("boom"))
    executor = AgentExecutor()

    executor.execute(agent, AgentContext())

    assert agent.state == AgentState.FAILED


def test_failure_emits_started_then_failed():
    agent = _FakeAgent(raises=ValueError("boom"))
    executor = AgentExecutor()

    result = executor.execute(agent, AgentContext())

    assert _event_types(result) == [AgentEventType.STARTED, AgentEventType.FAILED]


# --- permission validation --------------------------------------------------------------


def test_no_policy_configured_allows_execution():
    agent = _FakeAgent()
    executor = AgentExecutor(permission_policy=None)

    result = executor.execute(agent, AgentContext())

    assert result.success is True


def test_deny_all_policy_raises_and_never_starts_execution():
    agent = _FakeAgent()
    executor = AgentExecutor(permission_policy=PermissionPolicy(deny_all=True))

    with pytest.raises(AgentPermissionError):
        executor.execute(agent, AgentContext())

    assert agent.state == AgentState.READY  # untouched - validation happens before any transition
    assert agent.executed_with is None


def test_missing_required_permission_raises():
    agent = _FakeAgent(granted_permissions=("memory:read",))
    executor = AgentExecutor(permission_policy=PermissionPolicy(required_permissions=("tools:execute",)))

    with pytest.raises(AgentPermissionError, match="tools:execute"):
        executor.execute(agent, AgentContext())


def test_granted_required_permission_allows_execution():
    agent = _FakeAgent(granted_permissions=("tools:execute",))
    executor = AgentExecutor(permission_policy=PermissionPolicy(required_permissions=("tools:execute",)))

    result = executor.execute(agent, AgentContext())

    assert result.success is True


def test_allow_all_bypasses_required_permissions_check():
    agent = _FakeAgent(granted_permissions=())
    executor = AgentExecutor(
        permission_policy=PermissionPolicy(allow_all=True, required_permissions=("tools:execute",))
    )

    result = executor.execute(agent, AgentContext())

    assert result.success is True
