import pytest

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentCapability, AgentState
from app.services.ai.agents.executive.dispatcher import Dispatcher
from app.services.ai.agents.executive.events import ExecutiveEventPublisher, ExecutiveEventType
from app.services.ai.agents.executive.executive_agent import ExecutiveAgent
from app.services.ai.agents.executive.policies import ExecutivePolicy
from app.services.ai.agents.executive.state import ExecutiveState
from app.services.ai.agents.factory import AgentFactory
from app.services.ai.agents.registry import AgentRegistry
from app.services.ai.agents.state import AgentStateMachine
from app.services.ai.agents.types import AgentIdentity
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeResponse
from app.services.ai.shared.execution_metadata import ExecutionMetadata
from app.services.context.types import ContextPackage
from app.services.prompt_builder.types import PromptPackage


class _FakeRuntime:
    def __init__(self, response=None, raises=None):
        self.response = response or RuntimeResponse(success=True)
        self.raises = raises
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        if self.raises is not None:
            raise self.raises
        return self.response


class _FakeRetrievalPipeline:
    def __init__(self, memories_package=None, conversations_package=None, raises=None):
        self.memories_package = memories_package or ContextPackage(
            sections=[], estimated_tokens=0, item_count=0, truncated=False
        )
        self.conversations_package = conversations_package or ContextPackage(
            sections=[], estimated_tokens=0, item_count=0, truncated=False
        )
        self.raises = raises
        self.memory_calls = []
        self.conversation_calls = []

    def search_memories(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.memory_calls.append((query, organization_id))
        if self.raises is not None:
            raise self.raises
        return self.memories_package

    def search_conversation_messages(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.conversation_calls.append((query, organization_id))
        return self.conversations_package


class _FakePromptBuilder:
    def __init__(self, package=None):
        self.package = package or PromptPackage(system_prompt="s")
        self.calls = []

    def build(self, query, context_package, conversation_history=None, system_prompt=None, additional_instructions=None):
        self.calls.append((query, context_package))
        return self.package


class _FakeDelegateAgent(BaseAgent):
    def __init__(self, name="memory-agent", capabilities=None, response=None):
        super().__init__(
            AgentIdentity(
                agent_id=name,
                name=name,
                display_name=name,
                capabilities=capabilities or AgentCapabilities(declared={AgentCapability.MEMORY}),
            ),
            state_machine=AgentStateMachine(initial=AgentState.READY),
        )
        self.response = response or RuntimeResponse(success=True)
        self.executed_with = []

    def initialize(self) -> None:
        return None

    def execute(self, context: AgentContext) -> RuntimeResponse:
        self.executed_with.append(context)
        return self.response

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
        return self.identity.capabilities

    def permissions(self) -> tuple[str, ...]:
        return ()

    def memory(self):
        return None

    def planner(self):
        return None

    def runtime(self) -> AIRuntime:
        return AIRuntime()


def _agent(**overrides):
    defaults = dict(
        runtime=_FakeRuntime(),
        retrieval_pipeline=_FakeRetrievalPipeline(),
        prompt_builder=_FakePromptBuilder(),
        default_provider=ProviderName.OPENAI,
    )
    defaults.update(overrides)
    return ExecutiveAgent(**defaults)


def _context(**overrides):
    defaults = dict(
        organization_id=1,
        agent_metadata=ExecutionMetadata(extra={"user_request": "Help me prepare for an Anthropic interview."}),
    )
    defaults.update(overrides)
    return AgentContext(**defaults)


# --- BaseAgent contract / registry / factory --------------------------------------------


def test_executive_agent_is_a_base_agent():
    assert isinstance(_agent(), BaseAgent)


def test_executive_agent_is_registered_as_the_default_system_agent():
    assert AgentRegistry.is_registered("executive")
    assert AgentRegistry.get("executive") is ExecutiveAgent


def test_executive_agent_can_be_constructed_via_the_factory():
    agent = AgentFactory.create(
        "executive",
        runtime=_FakeRuntime(),
        retrieval_pipeline=_FakeRetrievalPipeline(),
        prompt_builder=_FakePromptBuilder(),
    )

    assert isinstance(agent, ExecutiveAgent)


def test_capabilities_and_permissions_come_from_identity():
    agent = _agent()

    assert agent.capabilities() is agent.identity.capabilities
    assert agent.permissions() == agent.identity.permissions


def test_runtime_accessor_returns_the_injected_runtime():
    runtime = _FakeRuntime()
    agent = _agent(runtime=runtime)

    assert agent.runtime() is runtime


def test_planner_accessor_returns_the_executive_planner():
    agent = _agent()

    assert agent.planner() is agent._planner_instance


def test_memory_accessor_returns_none():
    assert _agent().memory() is None


def test_health_returns_true():
    assert _agent().health() is True


# --- execute() structural validation ------------------------------------------------------


def test_execute_raises_when_organization_id_is_missing():
    agent = _agent()

    with pytest.raises(ValueError, match="organization_id"):
        agent.execute(AgentContext())


# --- end-to-end execution flow ------------------------------------------------------------


def test_execute_runs_the_full_pipeline_and_returns_a_successful_runtime_response():
    runtime = _FakeRuntime(response=RuntimeResponse(success=True, provider=ProviderName.OPENAI))
    pipeline = _FakeRetrievalPipeline()
    builder = _FakePromptBuilder()
    agent = _agent(runtime=runtime, retrieval_pipeline=pipeline, prompt_builder=builder)

    response = agent.execute(_context())

    assert response.success is True
    assert len(pipeline.memory_calls) == 1
    assert pipeline.memory_calls[0] == ("Help me prepare for an Anthropic interview.", 1)
    assert len(builder.calls) == 1
    assert len(runtime.requests) == 1


def test_the_runtime_request_carries_the_organization_id_and_provider():
    runtime = _FakeRuntime()
    agent = _agent(runtime=runtime, default_provider=ProviderName.ANTHROPIC)

    agent.execute(_context(organization_id=42))

    request = runtime.requests[0]
    assert request.organization_id == 42
    assert request.provider == ProviderName.ANTHROPIC


def test_the_runtime_request_propagates_the_executions_shared_context_as_parent():
    runtime = _FakeRuntime()
    agent = _agent(runtime=runtime)
    context = _context()

    agent.execute(context)

    request = runtime.requests[0]
    assert request.parent_shared is context.shared


def test_without_a_conversation_id_only_memory_is_retrieved():
    pipeline = _FakeRetrievalPipeline()
    agent = _agent(retrieval_pipeline=pipeline)

    agent.execute(_context())

    assert len(pipeline.memory_calls) == 1
    assert len(pipeline.conversation_calls) == 0


def test_with_a_conversation_id_both_memory_and_conversations_are_retrieved():
    pipeline = _FakeRetrievalPipeline()
    agent = _agent(retrieval_pipeline=pipeline)

    agent.execute(_context(conversation_id=7))

    assert len(pipeline.memory_calls) == 1
    assert len(pipeline.conversation_calls) == 1


def test_the_final_response_is_the_generate_response_tasks_runtime_response():
    expected = RuntimeResponse(success=True, provider=ProviderName.OPENAI, usage=None)
    agent = _agent(runtime=_FakeRuntime(response=expected))

    response = agent.execute(_context())

    assert response is expected


def test_executive_state_ends_at_idle_after_a_successful_run():
    agent = _agent()

    agent.execute(_context())

    assert agent.executive_state.state == ExecutiveState.IDLE


# --- event emission -------------------------------------------------------------------------


def test_events_are_emitted_starting_with_plan_created_and_ending_with_response_generated():
    events = []
    publisher = ExecutiveEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)

    agent.execute(_context())

    event_types = [event.event_type for event in events]
    assert event_types[0] == ExecutiveEventType.PLAN_CREATED
    assert event_types[-1] == ExecutiveEventType.RESPONSE_GENERATED
    assert ExecutiveEventType.TASK_CREATED in event_types
    assert ExecutiveEventType.TASK_COMPLETED in event_types


def test_every_event_carries_the_executions_execution_id_and_correlation_id():
    events = []
    publisher = ExecutiveEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    context = _context()

    agent.execute(context)

    assert all(event.execution_id == context.execution_id for event in events)
    assert all(event.correlation_id == context.correlation_id for event in events)


# --- failure handling -----------------------------------------------------------------------


def test_a_failing_runtime_call_produces_a_failed_response_not_a_raised_exception():
    agent = _agent(runtime=_FakeRuntime(raises=ValueError("provider exploded")))

    response = agent.execute(_context())  # must not raise

    assert response.success is False


def test_a_failing_runtime_call_leaves_the_executive_ready_for_the_next_request():
    agent = _agent(runtime=_FakeRuntime(raises=ValueError("boom")))

    agent.execute(_context())

    assert agent.executive_state.state == ExecutiveState.IDLE


def test_a_failing_task_emits_task_failed():
    events = []
    publisher = ExecutiveEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher, runtime=_FakeRuntime(raises=ValueError("boom")))

    agent.execute(_context())

    assert ExecutiveEventType.TASK_FAILED in [event.event_type for event in events]


def test_a_failing_retrieval_task_stops_the_pipeline_before_calling_the_runtime():
    runtime = _FakeRuntime()
    pipeline = _FakeRetrievalPipeline(raises=RuntimeError("vector store unavailable"))
    agent = _agent(runtime=runtime, retrieval_pipeline=pipeline)

    response = agent.execute(_context())

    assert response.success is False
    assert len(runtime.requests) == 0


# --- delegation / dispatch integration -------------------------------------------------------


def test_a_registered_known_agent_with_the_memory_capability_handles_retrieval_instead_of_the_pipeline():
    memory_agent = _FakeDelegateAgent(
        "memory-specialist",
        capabilities=AgentCapabilities(declared={AgentCapability.MEMORY}),
        response=RuntimeResponse(success=True),
    )
    pipeline = _FakeRetrievalPipeline()
    agent = _agent(retrieval_pipeline=pipeline, known_agents={"memory-specialist": memory_agent})

    agent.execute(_context())

    assert len(memory_agent.executed_with) == 1
    assert len(pipeline.memory_calls) == 0  # delegated away, never called directly


def test_delegation_propagates_delegation_depth_and_parent_agent_id():
    memory_agent = _FakeDelegateAgent("memory-specialist")
    agent = _agent(known_agents={"memory-specialist": memory_agent})

    agent.execute(_context())

    delegated_context = memory_agent.executed_with[0]
    assert delegated_context.delegation_depth == 1
    assert delegated_context.parent_agent_id == agent.identity.agent_id


def test_delegation_beyond_maximum_depth_fails_the_task():
    memory_agent = _FakeDelegateAgent("memory-specialist")
    policy = ExecutivePolicy(maximum_depth=0)
    agent = _agent(known_agents={"memory-specialist": memory_agent}, policy=policy)

    response = agent.execute(_context())

    assert response.success is False
    assert memory_agent.executed_with == []


def test_allow_delegation_false_prevents_any_dispatch():
    memory_agent = _FakeDelegateAgent("memory-specialist")
    pipeline = _FakeRetrievalPipeline()
    policy = ExecutivePolicy(allow_delegation=False)
    agent = _agent(known_agents={"memory-specialist": memory_agent}, policy=policy, retrieval_pipeline=pipeline)

    agent.execute(_context())

    assert memory_agent.executed_with == []
    assert len(pipeline.memory_calls) == 1  # handled directly instead


# --- Open/Closed: registering a new agent needs no ExecutiveAgent/Dispatcher change -------


def test_registering_a_brand_new_agent_type_requires_no_executive_or_dispatcher_modification():
    class _BrandNewResearchAgent(_FakeDelegateAgent):
        pass

    research_agent = _BrandNewResearchAgent(
        "brand-new-research", capabilities=AgentCapabilities(declared={AgentCapability.RESEARCH})
    )
    dispatcher = Dispatcher()  # the exact, unmodified Dispatcher class
    agent = _agent(dispatcher=dispatcher, known_agents={"brand-new-research": research_agent})

    # nothing about ExecutiveAgent or Dispatcher needed to change for this
    # new agent type to exist and be dispatchable by capability
    response = agent.execute(_context())

    assert response.success is True
