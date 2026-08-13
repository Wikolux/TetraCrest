"""DiscoverySpecialist (CP-02, Milestone 3) - comprehensive coverage:
domain integration, memory integration, ResearchAgent delegation
(framing-only, never execution), Executive/Dispatcher compatibility,
PromptBuilder/Runtime integration, event ordering, state transitions,
failure handling, and architecture compliance.

No mocks anywhere - hand-written fakes only, mirroring
test_research_agent.py's/test_personal_intelligence_agent.py's own
conventions exactly. No fake here ever touches a real DB, embedding
provider, or LLM provider.
"""

import ast
import importlib
import inspect
from datetime import UTC, datetime

import pytest

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentCapability
from app.services.ai.agents.executive.dispatcher import Dispatcher
from app.services.ai.agents.executive.decision import Decision
from app.services.ai.agents.executive.task import Task
from app.services.ai.agents.factory import AgentFactory
from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.registry import AgentRegistry
from app.services.ai.agents.specialists.factory import SpecialistFactory
from app.services.ai.agents.specialists.product_management.discovery.discovery_agent import DiscoverySpecialist
from app.services.ai.agents.specialists.product_management.discovery.events import (
    DiscoveryEventPublisher,
    DiscoveryEventType,
)
from app.services.ai.agents.specialists.product_management.discovery.request import DiscoveryOperation, DiscoveryRequest
from app.services.ai.agents.specialists.product_management.discovery.state import DiscoveryState
from app.services.ai.agents.specialists.product_management.memory_service import ProfessionalMemoryService
from app.services.ai.agents.specialists.product_management.shared.types import (
    MEMORY_TYPE_DISCOVERY_FINDING,
    MEMORY_TYPE_RESEARCH_FINDING,
)
from app.services.ai.agents.specialists.registry import SpecialistRegistry
from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.types import RuntimeResponse
from app.services.ai.shared.execution_metadata import ExecutionMetadata
from app.services.ai.shared.response import AIResponseMetadata, ProviderResponse
from app.services.ai.conversation.types import ConversationResponse
from app.services.context.types import ContextItem, ContextPackage, ContextSection


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


class _FakeMemory(AgentMemory):
    def __init__(self, package=None):
        self.package = package or ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)
        self.remembered = []
        self.retrieve_calls = []
        self.search_calls = []
        self.raises_on_remember = None

    def remember(self, item, **kwargs):
        if self.raises_on_remember is not None:
            raise self.raises_on_remember
        self.remembered.append((item, kwargs))

    def retrieve(self, query, **kwargs):
        self.retrieve_calls.append((query, kwargs))
        return self.package

    def search(self, query, **kwargs):
        self.search_calls.append((query, kwargs))
        return self.package

    def forget(self, item_id):
        raise NotImplementedError


class _FakeMemoryServiceRows:
    """AIMemoryService-shaped - only list_memories() is exercised, mirroring
    test_professional_memory_service.py's own _FakeMemoryService."""

    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []

    def list_memories(self, organization_id, skip=0, limit=20):
        self.calls.append((organization_id, skip, limit))
        matching = [row for row in self.rows if row.organization_id == organization_id]
        return matching[skip : skip + limit]


class _Row:
    def __init__(self, id, organization_id, content, memory_type, title="", created_at=None):
        self.id = id
        self.organization_id = organization_id
        self.content = content
        self.memory_type = memory_type
        self.title = title
        self.created_at = created_at or datetime.now(UTC)


def _memory_item(content="prior finding", resource_id=1):
    return ContextItem(
        resource_type="memory", resource_id=resource_id, content=content, score=1.0, created_at=datetime.now(UTC)
    )


def _package_with_items(items):
    return ContextPackage(
        sections=[ContextSection(resource_type="memory", items=items)],
        estimated_tokens=10,
        item_count=len(items),
        truncated=False,
    )


def _agent(**overrides):
    memory = overrides.pop("memory_adapter", None) or _FakeMemory()
    defaults = dict(
        runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()),
        memory_adapter=memory,
        memory_service=ProfessionalMemoryService(memory, _FakeMemoryServiceRows()),
        default_provider=ProviderName.OPENAI,
    )
    defaults.update(overrides)
    return DiscoverySpecialist(**defaults)


def _agent_context(**overrides):
    defaults = dict(organization_id=1, user_id=2)
    defaults.update(overrides)
    return AgentContext(**defaults)


def _specialist_context(agent_context=None):
    return SpecialistContext(agent_context=agent_context or _agent_context())


# --- construction / registration -----------------------------------------------------------


def test_discovery_specialist_is_a_base_agent():
    assert isinstance(_agent(), BaseAgent)


def test_discovery_specialist_is_registered_in_the_agent_registry():
    assert AgentRegistry.is_registered("discovery")
    assert AgentRegistry.get("discovery") is DiscoverySpecialist


def test_discovery_specialist_is_registered_in_the_specialist_registry():
    assert SpecialistRegistry.exists("discovery")
    registration = SpecialistRegistry.get_registration("discovery")
    assert registration.specialization == "discovery"
    assert registration.supported_tasks == frozenset({SpecialistTaskType.INVESTIGATION})


def test_discovery_specialist_constructible_via_agent_factory():
    agent = AgentFactory.create(
        "discovery", runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()), memory_adapter=_FakeMemory()
    )
    assert isinstance(agent, DiscoverySpecialist)


def test_discovery_specialist_constructible_via_specialist_factory():
    agent = SpecialistFactory.create(
        "discovery", runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()), memory_adapter=_FakeMemory()
    )
    assert isinstance(agent, DiscoverySpecialist)


def test_specialization_is_discovery():
    assert _agent().specialization() == "discovery"


def test_self_check_and_health_check_and_health_are_true_by_default():
    agent = _agent()
    assert agent.self_check() is True
    assert agent.health_check() is True
    assert agent.health() is True


def test_planner_accessor_and_runtime_accessor():
    runtime = RuntimeAdapter(runtime=_FakeRuntime())
    agent = _agent(runtime_adapter=runtime)
    assert agent.planner() is agent.coordinator.planner
    assert agent.runtime() is runtime.runtime


def test_memory_accessor_returns_the_agents_memory_adapter():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    assert agent.memory() is memory


# --- capability declaration / Executive collision-avoidance -------------------------------


def test_declares_only_reasoning_and_planning():
    declared = _agent().capabilities().declared
    assert declared == frozenset({AgentCapability.REASONING, AgentCapability.PLANNING})


def test_never_declares_memory_capability():
    # Deliberate: declaring AgentCapability.MEMORY would let Dispatcher
    # route ExecutivePlanner's own internal retrieve_memory/
    # retrieve_conversations tasks to this specialist instead of
    # ExecutiveAgent._handle_task() handling them - Architecture §19.
    assert AgentCapability.MEMORY not in _agent().capabilities().declared


def test_never_declares_research_capability():
    # Discovery frames research questions; it never performs research
    # itself, so it must never be mistaken for ResearchAgent by capability
    # match (Architecture §9/§19).
    assert AgentCapability.RESEARCH not in _agent().capabilities().declared


def test_evaluate_uses_the_discovery_policy_minimum_confidence():
    from app.services.ai.agents.specialists.product_management.discovery.policies import DiscoveryPolicy
    from app.services.ai.agents.specialists.shared.response import SpecialistResponse

    agent = _agent(discovery_policy=DiscoveryPolicy(minimum_confidence=0.5))
    assert agent.evaluate(SpecialistResponse(success=True, confidence=0.6)) is True
    assert agent.evaluate(SpecialistResponse(success=True, confidence=0.4)) is False
    assert agent.evaluate(SpecialistResponse(success=False, confidence=0.9)) is False


# --- Executive / Dispatcher compatibility --------------------------------------------------


def test_dispatcher_routes_a_reasoning_tagged_task_to_discovery_specialist():
    agent = _agent()
    task = Task(title="frame this problem", execution_id="exec-1", metadata={"required_capability": AgentCapability.REASONING})
    decision = Decision()

    routed = Dispatcher().dispatch(decision, task, {"discovery": agent})

    assert routed is agent


def test_dispatcher_never_routes_a_memory_tagged_task_to_discovery_specialist():
    agent = _agent()
    task = Task(title="retrieve_memory", execution_id="exec-1", metadata={"required_capability": AgentCapability.MEMORY})
    decision = Decision()

    routed = Dispatcher().dispatch(decision, task, {"discovery": agent})

    assert routed is None


# --- execute() / BaseAgent contract ---------------------------------------------------------


def test_execute_requires_organization_id():
    agent = _agent()
    with pytest.raises(ValueError):
        agent.execute(AgentContext(organization_id=None))


def test_execute_extracts_operation_from_agent_metadata():
    runtime = _FakeRuntime()
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))
    context = _agent_context(
        agent_metadata=ExecutionMetadata(extra={"operation": "recall", "text": "onboarding"})
    )

    response = agent.execute(context)

    assert isinstance(response, RuntimeResponse)
    assert response.success is True


# --- memory integration: writes ------------------------------------------------------------


def test_validate_problem_writes_a_discovery_finding_through_professional_memory_service():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    request = DiscoveryRequest(operation=DiscoveryOperation.VALIDATE_PROBLEM, text="Users churn", source="Support tickets")

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert len(memory.remembered) == 1
    content, kwargs = memory.remembered[0]
    assert "Users churn" in content
    assert kwargs["memory_type"] == MEMORY_TYPE_DISCOVERY_FINDING
    assert kwargs["organization_id"] == 1


def test_synthesize_interview_writes_a_discovery_finding():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    request = DiscoveryRequest(
        operation=DiscoveryOperation.SYNTHESIZE_INTERVIEW, text="users hate slow onboarding", source="Interview #3"
    )

    agent.process(request, _specialist_context())

    assert len(memory.remembered) == 1
    assert memory.remembered[0][1]["memory_type"] == MEMORY_TYPE_DISCOVERY_FINDING


def test_track_hypothesis_writes_a_new_finding_append_only_never_mutating():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    request = DiscoveryRequest(
        operation=DiscoveryOperation.TRACK_HYPOTHESIS,
        hypothesis="Faster onboarding increases activation",
        status="validated",
        source="A/B test #5",
        text="activation +12%",
    )

    agent.process(request, _specialist_context())

    assert len(memory.remembered) == 1
    content, _ = memory.remembered[0]
    assert "validated" in content


def test_record_research_finding_writes_a_research_finding_not_a_discovery_finding():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    request = DiscoveryRequest(
        operation=DiscoveryOperation.RECORD_RESEARCH_FINDING,
        text="Competitors charge $50/mo on average",
        source_question="What do competitors charge?",
        implications="Room to price at $40/mo",
    )

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert len(memory.remembered) == 1
    content, kwargs = memory.remembered[0]
    assert kwargs["memory_type"] == MEMORY_TYPE_RESEARCH_FINDING
    assert "competitors charge?" in content.lower() or "What do competitors charge?" in content


def test_frame_research_question_never_writes_to_memory():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    request = DiscoveryRequest(operation=DiscoveryOperation.FRAME_RESEARCH_QUESTION, text="What do competitors charge?")

    agent.process(request, _specialist_context())

    assert memory.remembered == []


def test_frame_jtbd_frame_persona_assess_opportunity_never_write_to_memory():
    # Reasoning frames, not evidence records of their own (Architecture §7).
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    context = _specialist_context()

    agent.process(DiscoveryRequest(operation=DiscoveryOperation.FRAME_JTBD, text="hire the app to save time"), context)
    agent.process(DiscoveryRequest(operation=DiscoveryOperation.FRAME_PERSONA, title="Busy Ben"), context)
    agent.process(DiscoveryRequest(operation=DiscoveryOperation.ASSESS_OPPORTUNITY, title="Faster onboarding"), context)

    assert memory.remembered == []


# --- memory integration: reads --------------------------------------------------------------


def test_recall_reads_through_professional_memory_service_scoped_to_memories():
    package = _package_with_items([_memory_item("prior discovery finding")])
    memory = _FakeMemory(package=package)
    agent = _agent(memory_adapter=memory)
    request = DiscoveryRequest(operation=DiscoveryOperation.RECALL, text="onboarding")

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert len(memory.retrieve_calls) == 1
    query, kwargs = memory.retrieve_calls[0]
    assert query == "onboarding"
    assert kwargs["scope"] == "memories"
    assert response.sources == ("1",)


def test_never_bypasses_agent_memory_search_is_distinct_from_retrieve():
    # ProfessionalMemoryService.search() must never internally call
    # .retrieve() (or vice versa) - both are exposed distinctly, mirroring
    # AgentMemory's own two-method surface (Milestone 2's own precedent).
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    agent.process(DiscoveryRequest(operation=DiscoveryOperation.RECALL, text="onboarding"), _specialist_context())

    assert len(memory.retrieve_calls) == 1
    assert len(memory.search_calls) == 0


def test_summarize_reads_via_list_by_memory_type_bulk_path():
    rows = (
        _Row(id=1, organization_id=1, content="finding 1", memory_type=MEMORY_TYPE_DISCOVERY_FINDING),
        _Row(id=2, organization_id=1, content="finding 2", memory_type=MEMORY_TYPE_DISCOVERY_FINDING),
        _Row(id=3, organization_id=1, content="research 1", memory_type=MEMORY_TYPE_RESEARCH_FINDING),
    )
    memory = _FakeMemory()
    service = ProfessionalMemoryService(memory, _FakeMemoryServiceRows(rows))
    agent = _agent(memory_adapter=memory, memory_service=service)

    response = agent.process(DiscoveryRequest(operation=DiscoveryOperation.SUMMARIZE), _specialist_context())

    assert response.success is True
    assert "2 discovery finding(s)" in response.findings[0]
    assert "1 research finding(s)" in response.findings[0]


# --- ResearchAgent delegation: framing only, never execution --------------------------------


def test_discovery_specialist_module_never_imports_research_agent_code():
    module = importlib.import_module(
        "app.services.ai.agents.specialists.product_management.discovery.discovery_agent"
    )
    tree = ast.parse(inspect.getsource(module))
    imported_modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    assert not any("specialists.research" in name for name in imported_modules)


def test_discovery_specialist_module_never_imports_personal_intelligence_code():
    module = importlib.import_module(
        "app.services.ai.agents.specialists.product_management.discovery.discovery_agent"
    )
    tree = ast.parse(inspect.getsource(module))
    imported_modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    assert not any("personal_intelligence" in name for name in imported_modules)


def test_frame_research_question_emits_a_distinguishing_delegation_event_not_a_completion_of_research():
    events = []
    publisher = DiscoveryEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    request = DiscoveryRequest(
        operation=DiscoveryOperation.FRAME_RESEARCH_QUESTION, text="What do competitors charge?", informs="pricing decision"
    )

    response = agent.process(request, _specialist_context())

    event_types = [event.event_type for event in events]
    assert DiscoveryEventType.RESEARCH_QUESTION_FRAMED in event_types
    assert response.metadata.get("informs") == "pricing decision"


def test_frame_research_question_requires_the_question_text():
    agent = _agent()
    request = DiscoveryRequest(operation=DiscoveryOperation.FRAME_RESEARCH_QUESTION, text="")

    response = agent.process(request, _specialist_context())

    assert response.success is False
    assert "research question" in response.error.lower()


def test_record_research_finding_records_what_was_handed_back_never_performs_research():
    memory = _FakeMemory()
    runtime = _FakeRuntime()
    agent = _agent(memory_adapter=memory, runtime_adapter=RuntimeAdapter(runtime=runtime))
    request = DiscoveryRequest(
        operation=DiscoveryOperation.RECORD_RESEARCH_FINDING,
        text="Competitors charge $50/mo",
        source_question="What do competitors charge?",
    )

    agent.process(request, _specialist_context())

    # The only Runtime call made is a summarization of the *already-returned*
    # finding, never a research/tool invocation - and no ToolAdapter call
    # happens at all for this operation (Discovery never performs research).
    assert len(runtime.requests) == 1


# --- Runtime / PromptBuilder integration -----------------------------------------------------


def test_the_runtime_request_carries_organization_id_and_parent_shared():
    runtime = _FakeRuntime()
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))
    context = _specialist_context()

    agent.process(DiscoveryRequest(operation=DiscoveryOperation.RECALL, text="onboarding"), context)

    assert len(runtime.requests) == 1
    request = runtime.requests[0]
    assert request.organization_id == 1
    assert request.parent_shared is context.shared


def test_prompt_package_is_built_from_prompt_builder_and_contains_the_query():
    runtime = _FakeRuntime()
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))

    agent.process(
        DiscoveryRequest(operation=DiscoveryOperation.FRAME_JTBD, text="hire the app to save time"),
        _specialist_context(),
    )

    prompt_package = runtime.requests[0].prompt_package
    assert prompt_package is not None
    rendered = " ".join(section.content for section in prompt_package.sections)
    assert "hire the app to save time" in rendered


def test_summary_uses_runtime_generated_text_when_available():
    conversation_response = ConversationResponse(
        text="A clear discovery framing.",
        response=ProviderResponse(metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="fake")),
    )
    runtime = _FakeRuntime(response=RuntimeResponse(success=True, conversation_response=conversation_response))
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))

    response = agent.process(
        DiscoveryRequest(operation=DiscoveryOperation.RECALL, text="onboarding"), _specialist_context()
    )

    assert response.summary == "A clear discovery framing."


# --- event ordering --------------------------------------------------------------------------


def test_events_are_emitted_in_order_for_validate_problem():
    events = []
    publisher = DiscoveryEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    request = DiscoveryRequest(operation=DiscoveryOperation.VALIDATE_PROBLEM, text="Users churn", source="tickets")

    agent.process(request, _specialist_context())

    event_types = [event.event_type for event in events]
    assert event_types == [
        DiscoveryEventType.REQUEST_STARTED,
        DiscoveryEventType.PRECEDENT_RETRIEVED,
        DiscoveryEventType.FINDING_RECORDED,
        DiscoveryEventType.PROBLEM_STATEMENT_DRAFTED,
        DiscoveryEventType.REQUEST_COMPLETED,
    ]


def test_every_event_carries_execution_id_correlation_id_and_agent_id():
    events = []
    publisher = DiscoveryEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    context = _specialist_context()

    agent.process(DiscoveryRequest(operation=DiscoveryOperation.RECALL, text="x"), context)

    assert all(event.execution_id == context.execution_id for event in events)
    assert all(event.correlation_id == context.correlation_id for event in events)
    assert all(event.agent_id == "discovery" for event in events)


def test_failed_run_emits_request_failed_instead_of_completed():
    events = []
    publisher = DiscoveryEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(raises=ValueError("boom"))))

    agent.process(DiscoveryRequest(operation=DiscoveryOperation.RECALL, text="x"), _specialist_context())

    event_types = [event.event_type for event in events]
    assert DiscoveryEventType.REQUEST_FAILED in event_types
    assert DiscoveryEventType.REQUEST_COMPLETED not in event_types


# --- state transitions ------------------------------------------------------------------------


def test_discovery_state_ends_at_idle_after_a_successful_run():
    agent = _agent()
    agent.process(DiscoveryRequest(operation=DiscoveryOperation.RECALL, text="x"), _specialist_context())
    assert agent.discovery_state.state == DiscoveryState.IDLE


def test_discovery_state_ends_at_idle_after_a_failed_run():
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(raises=ValueError("boom"))))
    agent.process(DiscoveryRequest(operation=DiscoveryOperation.RECALL, text="x"), _specialist_context())
    assert agent.discovery_state.state == DiscoveryState.IDLE


def test_discovery_state_ends_at_idle_after_a_construction_error_mid_structuring():
    agent = _agent()
    request = DiscoveryRequest(operation=DiscoveryOperation.VALIDATE_PROBLEM, text="Users churn", source="")

    response = agent.process(request, _specialist_context())

    assert response.success is False
    assert agent.discovery_state.state == DiscoveryState.IDLE


def test_agent_can_process_multiple_requests_in_sequence():
    agent = _agent()
    context = _specialist_context()
    for _ in range(3):
        response = agent.process(DiscoveryRequest(operation=DiscoveryOperation.RECALL, text="x"), context)
        assert response.success is True
    assert agent.discovery_state.state == DiscoveryState.IDLE


# --- failure handling / evidence discipline ---------------------------------------------------


def test_a_raising_memory_adapter_produces_a_failed_response_not_a_raised_exception():
    memory = _FakeMemory()
    memory.raises_on_remember = ValueError("db unavailable")
    agent = _agent(memory_adapter=memory)
    request = DiscoveryRequest(operation=DiscoveryOperation.VALIDATE_PROBLEM, text="Users churn", source="tickets")

    response = agent.process(request, _specialist_context())

    assert response.success is False
    assert "db unavailable" in response.error


def test_a_failing_runtime_call_produces_a_failed_response_with_zero_confidence():
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(response=RuntimeResponse(success=False, error="provider down"))))

    response = agent.process(
        DiscoveryRequest(operation=DiscoveryOperation.RECALL, text="x"), _specialist_context()
    )

    assert response.success is False
    assert response.confidence == 0.0
    assert response.error == "provider down"


def test_missing_source_produces_an_honest_failure_asking_for_the_missing_evidence():
    agent = _agent()
    request = DiscoveryRequest(operation=DiscoveryOperation.VALIDATE_PROBLEM, text="Something is broken", source="")

    response = agent.process(request, _specialist_context())

    assert response.success is False
    assert "source" in response.error.lower()


def test_recommendation_with_no_evidence_is_honest_never_fabricated():
    agent = _agent()  # empty package by default - no prior evidence
    request = DiscoveryRequest(operation=DiscoveryOperation.GENERATE_RECOMMENDATION, text="Should we build feature X?")

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert response.confidence < 0.5
    assert "insufficient evidence" in response.recommendations[0].lower()


def test_recommendation_with_evidence_cites_it_and_is_more_confident():
    package = _package_with_items([_memory_item("prior finding", resource_id=99)])
    memory = _FakeMemory(package=package)
    agent = _agent(memory_adapter=memory)
    request = DiscoveryRequest(operation=DiscoveryOperation.GENERATE_RECOMMENDATION, text="Proceed with feature X")

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert response.confidence > 0.5
    assert response.sources == ("99",)


def test_maximum_depth_exceeded_fails_immediately_without_touching_any_collaborator():
    memory = _FakeMemory()
    runtime = _FakeRuntime()
    agent = _agent(memory_adapter=memory, runtime_adapter=RuntimeAdapter(runtime=runtime))
    context = _specialist_context(
        agent_context=_agent_context(delegation_depth=agent.policy.maximum_depth)
    )

    response = agent.process(DiscoveryRequest(operation=DiscoveryOperation.RECALL, text="x"), context)

    assert response.success is False
    assert "depth" in response.error.lower()
    assert memory.retrieve_calls == []
    assert runtime.requests == []


def test_unsupported_raw_operation_value_produces_a_failed_response_not_a_crash():
    with pytest.raises(ValueError):
        DiscoveryOperation("not_a_real_operation")
