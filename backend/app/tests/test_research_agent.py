import pytest

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.factory import AgentFactory
from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.registry import AgentRegistry
from app.services.ai.agents.specialists.factory import SpecialistFactory
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
from app.services.ai.agents.specialists.registry import SpecialistRegistry
from app.services.ai.agents.specialists.research.events import ResearchEventPublisher, ResearchEventType
from app.services.ai.agents.specialists.research.research_agent import ResearchAgent
from app.services.ai.agents.specialists.research.state import ResearchState
from app.services.ai.agents.specialists.research.synthesizer import ResearchSynthesizer
from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.agents.specialists.shared.policies import RetryPolicy, SpecialistExecutionPolicy
from app.services.ai.agents.specialists.shared.request import SpecialistRequest
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType
from app.services.ai.agents.specialists.tool_adapter import ToolAdapter
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.cancellation import CancellationToken
from app.services.ai.runtime.types import RuntimeResponse
from app.services.ai.shared.execution_metadata import ExecutionMetadata
from app.services.ai.shared.response import AIResponseMetadata, ProviderResponse
from app.services.ai.tools.result import ToolResult
from app.services.context.types import ContextItem, ContextPackage, ContextSection
from app.services.ai.conversation.types import ConversationResponse
from datetime import UTC, datetime


class _FakeRuntime:
    def __init__(self, response=None, raises=None):
        self.response = response if response is not None else RuntimeResponse(success=True)
        self.raises = raises
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        if self.raises is not None:
            raise self.raises
        return self.response


class _FakePipeline:
    def __init__(self, package=None):
        self.package = package or ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)
        self.memory_calls = []
        self.conversation_calls = []
        self.all_calls = []

    def search_memories(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.memory_calls.append((query, organization_id))
        return self.package

    def search_conversation_messages(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.conversation_calls.append((query, organization_id))
        return self.package

    def search_all(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.all_calls.append((query, organization_id))
        return self.package


class _FakeToolManager:
    def __init__(self, result=None):
        self.result = result or ToolResult(success=True, output="tool output")
        self.calls = []

    def invoke(self, tool_id, parameters, **kwargs):
        self.calls.append((tool_id, parameters, kwargs))
        return self.result


def _agent(**overrides):
    defaults = dict(
        runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()),
        memory_adapter=MemoryAdapter(pipeline=_FakePipeline()),
        default_provider=ProviderName.OPENAI,
    )
    defaults.update(overrides)
    return ResearchAgent(**defaults)


def _agent_context(**overrides):
    defaults = dict(organization_id=1)
    defaults.update(overrides)
    return AgentContext(**defaults)


def _memory_item(content, resource_id=1):
    return ContextItem(
        resource_type="memory", resource_id=resource_id, content=content, score=1.0, created_at=datetime.now(UTC)
    )


def _memory_package(items):
    return ContextPackage(
        sections=[ContextSection(resource_type="memory", items=items)],
        estimated_tokens=10,
        item_count=len(items),
        truncated=False,
    )


# --- registry / factory integration -------------------------------------------------------


def test_research_agent_is_a_base_agent():
    assert isinstance(_agent(), BaseAgent)


def test_research_agent_is_registered_in_the_agent_registry():
    assert AgentRegistry.is_registered("research")
    assert AgentRegistry.get("research") is ResearchAgent


def test_research_agent_is_registered_in_the_specialist_registry():
    assert SpecialistRegistry.exists("research")
    registration = SpecialistRegistry.get_registration("research")
    assert registration.specialization == "research"
    assert SpecialistTaskType.RESEARCH in registration.supported_tasks


def test_research_agent_constructible_via_agent_factory():
    agent = AgentFactory.create(
        "research", runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()), memory_adapter=MemoryAdapter(pipeline=_FakePipeline())
    )
    assert isinstance(agent, ResearchAgent)


def test_research_agent_constructible_via_specialist_factory():
    agent = SpecialistFactory.create(
        "research", runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()), memory_adapter=MemoryAdapter(pipeline=_FakePipeline())
    )
    assert isinstance(agent, ResearchAgent)


# --- SpecialistAgent contract ------------------------------------------------------------


def test_specialization_is_research():
    assert _agent().specialization() == "research"


def test_supported_tasks_includes_every_documented_research_task():
    tasks = _agent().supported_tasks()

    assert tasks == {
        SpecialistTaskType.RESEARCH,
        SpecialistTaskType.ANALYSIS,
        SpecialistTaskType.SUMMARIZATION,
        SpecialistTaskType.COMPARISON,
        SpecialistTaskType.VERIFICATION,
        SpecialistTaskType.INVESTIGATION,
    }


def test_capabilities_and_permissions_come_from_identity():
    agent = _agent()

    assert agent.capabilities() is agent.identity.capabilities
    assert agent.permissions() == agent.identity.permissions


def test_planner_accessor_returns_the_coordinators_planner():
    agent = _agent()

    assert agent.planner() is agent.coordinator.planner


def test_runtime_accessor_returns_the_adapters_runtime():
    runtime = _FakeRuntime()
    adapter = RuntimeAdapter(runtime=runtime)
    agent = _agent(runtime_adapter=adapter)

    assert agent.runtime() is runtime


def test_memory_accessor_returns_the_agents_memory_adapter():
    # M20.6: MemoryAdapter now implements AgentMemory, so this accessor
    # exposes the same memory_adapter _retrieve_memory() uses internally,
    # rather than unconditionally returning None.
    agent = _agent()

    memory = agent.memory()

    assert memory is agent.coordinator.memory_adapter
    assert isinstance(memory, AgentMemory)


def test_self_check_and_health_check_and_health_are_true_by_default():
    agent = _agent()

    assert agent.self_check() is True
    assert agent.health_check() is True
    assert agent.health() is True


def test_evaluate_uses_the_research_policy_minimum_confidence():
    from app.services.ai.agents.specialists.research.policies import ResearchPolicy
    from app.services.ai.agents.specialists.shared.response import SpecialistResponse

    agent = _agent(research_policy=ResearchPolicy(minimum_confidence=0.5))

    assert agent.evaluate(SpecialistResponse(success=True, confidence=0.8)) is True
    assert agent.evaluate(SpecialistResponse(success=True, confidence=0.2)) is False
    assert agent.evaluate(SpecialistResponse(success=False, confidence=0.9)) is False


# --- execute() / BaseAgent contract satisfaction -----------------------------------------------


def test_execute_requires_organization_id():
    agent = _agent()

    with pytest.raises(ValueError, match="organization_id"):
        agent.execute(AgentContext())


def test_execute_extracts_the_objective_from_agent_metadata():
    pipeline = _FakePipeline()
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=pipeline))
    context = _agent_context(agent_metadata=ExecutionMetadata(extra={"objective": "Prepare for an interview"}))

    agent.execute(context)

    assert pipeline.all_calls == [("Prepare for an interview", 1)]


def test_execute_extracts_a_full_specialist_request_when_given():
    pipeline = _FakePipeline()
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=pipeline))
    request = SpecialistRequest(objective="Compare two frameworks", memory_allowed=True)
    context = _agent_context(agent_metadata=ExecutionMetadata(extra={"specialist_request": request}))

    agent.execute(context)

    assert pipeline.all_calls == [("Compare two frameworks", 1)]


def test_execute_returns_a_runtime_response():
    agent = _agent()
    context = _agent_context(agent_metadata=ExecutionMetadata(extra={"objective": "x"}))

    response = agent.execute(context)

    assert isinstance(response, RuntimeResponse)
    assert response.success is True


# --- full research() workflow -----------------------------------------------------------------


def test_research_runs_the_full_pipeline_and_returns_a_successful_response():
    runtime = _FakeRuntime(response=RuntimeResponse(success=True))
    pipeline = _FakePipeline(package=_memory_package([_memory_item("a fact")]))
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime), memory_adapter=MemoryAdapter(pipeline=pipeline))
    request = SpecialistRequest(objective="Prepare for an interview")

    from app.services.ai.agents.specialists.research.context import build_research_context

    specialist_context = build_research_context(_agent_context(), request)

    response = agent.research(request, specialist_context)

    assert response.success is True
    assert "a fact" in response.findings
    assert len(runtime.requests) == 1
    assert len(pipeline.all_calls) == 1


def test_research_skips_memory_retrieval_when_not_allowed():
    pipeline = _FakePipeline()
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=pipeline))
    request = SpecialistRequest(objective="x", memory_allowed=False)

    from app.services.ai.agents.specialists.research.context import build_research_context

    agent.research(request, build_research_context(_agent_context(), request))

    assert pipeline.all_calls == []


def test_research_never_invokes_tools_when_web_is_not_allowed():
    tool_manager = _FakeToolManager()
    agent = _agent(tool_adapter=ToolAdapter(manager=tool_manager))
    request = SpecialistRequest(objective="x", web_allowed=False)

    from app.services.ai.agents.specialists.research.context import build_research_context

    agent.research(request, build_research_context(_agent_context(), request))

    assert tool_manager.calls == []


def test_the_runtime_request_carries_organization_id_and_parent_shared():
    runtime = _FakeRuntime()
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime), default_provider=ProviderName.ANTHROPIC)
    request = SpecialistRequest(objective="x")

    from app.services.ai.agents.specialists.research.context import build_research_context

    context = build_research_context(_agent_context(organization_id=42), request)
    agent.research(request, context)

    runtime_request = runtime.requests[0]
    assert runtime_request.organization_id == 42
    assert runtime_request.provider == ProviderName.ANTHROPIC
    assert runtime_request.parent_shared is context.shared


def test_research_result_identity_matches_the_context():
    agent = _agent()
    request = SpecialistRequest(objective="x")

    from app.services.ai.agents.specialists.research.context import build_research_context

    context = build_research_context(_agent_context(), request)
    response = agent.research(request, context)

    assert response.execution_id == context.execution_id
    assert response.correlation_id == context.correlation_id
    assert response.parent_execution_id == context.parent_execution_id


def test_research_state_ends_at_idle_after_a_successful_run():
    agent = _agent()
    request = SpecialistRequest(objective="x")

    from app.services.ai.agents.specialists.research.context import build_research_context

    agent.research(request, build_research_context(_agent_context(), request))

    assert agent.research_state.state == ResearchState.IDLE


def test_executive_summary_uses_runtime_generated_text_when_available():
    conversation_response = ConversationResponse(
        text="Here is your interview prep.",
        response=ProviderResponse(metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="fake")),
    )
    runtime = _FakeRuntime(response=RuntimeResponse(success=True, conversation_response=conversation_response))
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))
    request = SpecialistRequest(objective="Prepare for an interview")

    from app.services.ai.agents.specialists.research.context import build_research_context

    response = agent.research(request, build_research_context(_agent_context(), request))

    assert response.summary == "Here is your interview prep."


def test_executive_summary_falls_back_to_the_objective_without_runtime_text():
    agent = _agent()
    request = SpecialistRequest(objective="Prepare for an interview")

    from app.services.ai.agents.specialists.research.context import build_research_context

    response = agent.research(request, build_research_context(_agent_context(), request))

    assert response.summary == "Prepare for an interview"


# --- events --------------------------------------------------------------------------------


def test_events_are_emitted_in_order_for_a_successful_run():
    events = []
    publisher = ResearchEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    request = SpecialistRequest(objective="x")

    from app.services.ai.agents.specialists.research.context import build_research_context

    agent.research(request, build_research_context(_agent_context(), request))

    event_types = [event.event_type for event in events]
    assert event_types == [
        ResearchEventType.RESEARCH_STARTED,
        ResearchEventType.PLAN_CREATED,
        ResearchEventType.MEMORY_RETRIEVED,
        ResearchEventType.TOOLS_COMPLETED,
        ResearchEventType.SYNTHESIS_COMPLETED,
        ResearchEventType.REPORT_GENERATED,
        ResearchEventType.RESEARCH_COMPLETED,
    ]


def test_every_event_carries_execution_id_correlation_id_and_agent_id():
    events = []
    publisher = ResearchEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    request = SpecialistRequest(objective="x")

    from app.services.ai.agents.specialists.research.context import build_research_context

    context = build_research_context(_agent_context(), request)
    agent.research(request, context)

    assert all(event.execution_id == context.execution_id for event in events)
    assert all(event.correlation_id == context.correlation_id for event in events)
    assert all(event.agent_id == "research" for event in events)


def test_failed_run_emits_research_failed_instead_of_completed():
    events = []
    publisher = ResearchEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(raises=ValueError("boom"))))
    request = SpecialistRequest(objective="x")

    from app.services.ai.agents.specialists.research.context import build_research_context

    agent.research(request, build_research_context(_agent_context(), request))

    event_types = [event.event_type for event in events]
    assert ResearchEventType.RESEARCH_FAILED in event_types
    assert ResearchEventType.RESEARCH_COMPLETED not in event_types


# --- failure handling -----------------------------------------------------------------------


def test_a_raising_memory_adapter_produces_a_failed_response_not_a_raised_exception():
    class _RaisingPipeline:
        def search_all(self, *args, **kwargs):
            raise RuntimeError("vector store unavailable")

    agent = _agent(memory_adapter=MemoryAdapter(pipeline=_RaisingPipeline()))
    request = SpecialistRequest(objective="x")

    from app.services.ai.agents.specialists.research.context import build_research_context

    response = agent.research(request, build_research_context(_agent_context(), request))  # must not raise

    assert response.success is False
    assert "vector store unavailable" in response.error


def test_a_failing_runtime_call_produces_a_failed_response():
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(response=RuntimeResponse(success=False, error="provider down"))))
    request = SpecialistRequest(objective="x")

    from app.services.ai.agents.specialists.research.context import build_research_context

    response = agent.research(request, build_research_context(_agent_context(), request))

    assert response.success is False
    assert response.error == "provider down"


def test_research_state_ends_at_idle_after_a_failed_run():
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(raises=ValueError("boom"))))
    request = SpecialistRequest(objective="x")

    from app.services.ai.agents.specialists.research.context import build_research_context

    agent.research(request, build_research_context(_agent_context(), request))

    assert agent.research_state.state == ResearchState.IDLE


# --- maximum depth policy --------------------------------------------------------------------


def test_maximum_depth_exceeded_fails_immediately_without_touching_any_collaborator():
    runtime = _FakeRuntime()
    pipeline = _FakePipeline()
    agent = _agent(
        runtime_adapter=RuntimeAdapter(runtime=runtime),
        memory_adapter=MemoryAdapter(pipeline=pipeline),
        policy=SpecialistExecutionPolicy(maximum_depth=1),
    )
    request = SpecialistRequest(objective="x")

    from app.services.ai.agents.context import AgentContext as _AgentContext
    from app.services.ai.agents.specialists.research.context import build_research_context

    deep_context = build_research_context(_AgentContext(organization_id=1, delegation_depth=1), request)
    response = agent.research(request, deep_context)

    assert response.success is False
    assert "depth" in response.error.lower()
    assert runtime.requests == []
    assert pipeline.all_calls == []


# --- retry policy wiring (architectural fix) --------------------------------------------------


def test_the_agents_retry_policy_actually_governs_tool_execution():
    # confirms self.policy.retry_policy is genuinely wired into tool
    # execution, not just a declared-but-unused field
    from app.services.ai.tools.base_tool import BaseTool
    from app.services.ai.tools.context import ToolContext as _ToolContext
    from app.services.ai.tools.enums import ToolCapability, ToolCategory as _ToolCategory
    from app.services.ai.tools.registry import ToolRegistry
    from app.services.ai.tools.schema import ToolSchema

    class _FlakyTool(BaseTool):
        attempts = 0

        @property
        def tool_id(self):
            return "flaky-search"

        @property
        def name(self):
            return "Flaky Search"

        @property
        def description(self):
            return ""

        @property
        def version(self):
            return "1.0"

        @property
        def category(self):
            return _ToolCategory.SEARCH

        @property
        def capabilities(self):
            return frozenset({ToolCapability.SEARCH})

        @property
        def permissions(self):
            return frozenset()

        def input_schema(self):
            return ToolSchema()

        def output_schema(self):
            return ToolSchema()

        def validate(self, parameters):
            return None

        def execute(self, context: _ToolContext):
            from app.services.ai.tools.result import ToolResult as _ToolResult

            type(self).attempts += 1
            if type(self).attempts <= 1:
                raise ValueError("transient")
            return _ToolResult(success=True, output="found it")

        def health_check(self):
            return True

    original = dict(ToolRegistry._providers)
    ToolRegistry.clear()
    try:
        ToolRegistry.register(
            "flaky-search", _FlakyTool, name="Flaky Search", category=_ToolCategory.SEARCH,
            capabilities={ToolCapability.SEARCH},
        )

        agent = _agent(policy=SpecialistExecutionPolicy(retry_policy=RetryPolicy(max_attempts=2)))
        request = SpecialistRequest(objective="x", web_allowed=True)

        from app.services.ai.agents.specialists.research.context import build_research_context

        response = agent.research(request, build_research_context(_agent_context(), request))

        assert response.success is True
        assert _FlakyTool.attempts == 2
    finally:
        ToolRegistry.clear()
        ToolRegistry._providers.update(original)


# --- cancellation propagation ------------------------------------------------------------------


def test_cancellation_token_is_propagated_to_tool_invocation():
    tool_manager = _FakeToolManager()
    agent = _agent(tool_adapter=ToolAdapter(manager=tool_manager))
    request = SpecialistRequest(objective="x", web_allowed=True)
    token = CancellationToken()


    # force _required_tools to find something by faking discovery via a
    # registered tool is unnecessary here - we directly verify propagation
    # by monkeypatching _required_tools to return a fixed tool id
    agent._required_tools = lambda req: ("some-tool",)  # noqa: SLF001 - test-only override

    from app.services.ai.agents.specialists.research.context import build_research_context

    agent.research(request, build_research_context(_agent_context(), request), cancellation_token=token)

    assert tool_manager.calls[0][2]["cancellation_token"] is token


# --- determinism / immutability ---------------------------------------------------------------


def test_research_does_not_mutate_the_request_or_context():
    agent = _agent()
    request = SpecialistRequest(objective="x", constraints=("a",))

    from app.services.ai.agents.specialists.research.context import build_research_context

    context = build_research_context(_agent_context(), request)
    agent.research(request, context)

    assert request.objective == "x"
    assert request.constraints == ("a",)
    assert context.request is request


def test_synthesizer_is_pure_and_produces_the_same_output_for_the_same_inputs():
    package = _memory_package([_memory_item("fact")])
    synthesizer = ResearchSynthesizer()

    first = synthesizer.synthesize(package, (), None)
    second = synthesizer.synthesize(package, (), None)

    assert first == second
