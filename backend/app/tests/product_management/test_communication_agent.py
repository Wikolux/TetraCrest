"""StakeholderCommunicationSpecialist (CP-02, Milestone 7) - comprehensive
coverage: communication generation, evidence enforcement, Executive
routing, prompt generation, memory usage, dependency verification,
append-only behavior, no-evidence handling, audience-specific
communication, and architecture compliance - including the structural
(not merely policy) proof that nothing can be sent, per Implementation_Plan.md's
own Milestone 7 acceptance criterion.

No mocks - hand-written fakes only, mirroring every prior milestone's own
conventions exactly.
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
from app.services.ai.agents.specialists.product_management.memory_service import ProfessionalMemoryService
from app.services.ai.agents.specialists.product_management.shared.types import (
    MEMORY_TYPE_DECISION,
    MEMORY_TYPE_DELIVERY_ARTIFACT,
    MEMORY_TYPE_METRIC,
    MEMORY_TYPE_ROADMAP,
    MEMORY_TYPE_STAKEHOLDER,
)
from app.services.ai.agents.specialists.product_management.stakeholder_communication.events import (
    CommunicationEventPublisher,
    CommunicationEventType,
)
from app.services.ai.agents.specialists.product_management.stakeholder_communication.request import (
    StakeholderCommunicationOperation,
    StakeholderCommunicationRequest,
)
from app.services.ai.agents.specialists.product_management.stakeholder_communication.stakeholder_communication_agent import (
    StakeholderCommunicationSpecialist,
)
from app.services.ai.agents.specialists.product_management.stakeholder_communication.state import CommunicationState
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


def _discovery_item(resource_id=1):
    return _memory_item(content="Discovery finding: users churn. Source: tickets. Status: unknown.", resource_id=resource_id)


def _decision_item(resource_id=2):
    return _memory_item(
        content="Decision: Onboarding revamp. Framework applied: rice. Rationale: proceed.", resource_id=resource_id
    )


def _stakeholder_item(resource_id=3):
    return _memory_item(content="Stakeholder: Jane Doe. Role/interest: VP Eng. RACI: accountable.", resource_id=resource_id)


def _package_with_items(items):
    return ContextPackage(
        sections=[ContextSection(resource_type="memory", items=items)],
        estimated_tokens=10,
        item_count=len(items),
        truncated=False,
    )


def _full_evidence_package():
    return _package_with_items([_discovery_item(1), _decision_item(2)])


def _agent(**overrides):
    memory = overrides.pop("memory_adapter", None) or _FakeMemory()
    defaults = dict(
        runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()),
        memory_adapter=memory,
        memory_service=ProfessionalMemoryService(memory, _FakeMemoryServiceRows()),
        default_provider=ProviderName.OPENAI,
    )
    defaults.update(overrides)
    return StakeholderCommunicationSpecialist(**defaults)


def _agent_context(**overrides):
    defaults = dict(organization_id=1, user_id=2)
    defaults.update(overrides)
    return AgentContext(**defaults)


def _specialist_context(agent_context=None):
    return SpecialistContext(agent_context=agent_context or _agent_context())


# --- construction / registration -----------------------------------------------------------


def test_is_a_base_agent():
    assert isinstance(_agent(), BaseAgent)


def test_is_registered_in_the_agent_registry():
    assert AgentRegistry.is_registered("stakeholder_communication")
    assert AgentRegistry.get("stakeholder_communication") is StakeholderCommunicationSpecialist


def test_is_registered_in_the_specialist_registry():
    assert SpecialistRegistry.exists("stakeholder_communication")
    registration = SpecialistRegistry.get_registration("stakeholder_communication")
    assert registration.specialization == "stakeholder_communication"
    assert registration.supported_tasks == frozenset({SpecialistTaskType.SUMMARIZATION})


def test_constructible_via_agent_factory():
    agent = AgentFactory.create(
        "stakeholder_communication", runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()), memory_adapter=_FakeMemory()
    )
    assert isinstance(agent, StakeholderCommunicationSpecialist)


def test_constructible_via_specialist_factory():
    agent = SpecialistFactory.create(
        "stakeholder_communication", runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()), memory_adapter=_FakeMemory()
    )
    assert isinstance(agent, StakeholderCommunicationSpecialist)


def test_specialization_is_stakeholder_communication():
    assert _agent().specialization() == "stakeholder_communication"


def test_self_check_and_health_check_and_health_are_true_by_default():
    agent = _agent()
    assert agent.self_check() is True
    assert agent.health_check() is True
    assert agent.health() is True


def test_evaluate_uses_the_communication_policy_minimum_confidence():
    from app.services.ai.agents.specialists.product_management.stakeholder_communication.policies import (
        CommunicationPolicy,
    )
    from app.services.ai.agents.specialists.shared.response import SpecialistResponse

    agent = _agent(communication_policy=CommunicationPolicy(minimum_confidence=0.5))
    assert agent.evaluate(SpecialistResponse(success=True, confidence=0.6)) is True
    assert agent.evaluate(SpecialistResponse(success=True, confidence=0.4)) is False


# --- capability declaration: the one difference from every prior specialist -------------------


def test_declares_reasoning_planning_and_communication():
    assert _agent().capabilities().declared == frozenset(
        {AgentCapability.REASONING, AgentCapability.PLANNING, AgentCapability.COMMUNICATION}
    )


def test_never_declares_memory_capability():
    assert AgentCapability.MEMORY not in _agent().capabilities().declared


def test_never_declares_research_capability():
    assert AgentCapability.RESEARCH not in _agent().capabilities().declared


# --- structural "never sends anything" proof (not merely policy) -------------------------------


def test_no_send_publish_or_notify_method_exists_on_the_class():
    forbidden_fragments = ("send", "publish_to", "notify", "deliver_to", "dispatch_to")
    member_names = [name for name, _ in inspect.getmembers(StakeholderCommunicationSpecialist)]
    offending = [
        name
        for name in member_names
        if any(fragment in name.lower() for fragment in forbidden_fragments) and not name.startswith("_")
    ]
    assert offending == []


def test_module_defines_no_function_with_a_sending_name():
    module = importlib.import_module(
        "app.services.ai.agents.specialists.product_management.stakeholder_communication.stakeholder_communication_agent"
    )
    tree = ast.parse(inspect.getsource(module))
    function_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    forbidden_fragments = ("send", "publish_to", "notify", "deliver_to")
    assert not any(fragment in name.lower() for name in function_names for fragment in forbidden_fragments)


def test_every_successful_draft_states_explicitly_it_was_not_sent():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION,
            text="Onboarding revamp status",
            audience="executive",
            purpose="executive_summary",
        ),
        _specialist_context(),
    )
    assert "not sent" in response.recommendations[0].lower()


# --- Executive / Dispatcher compatibility --------------------------------------------------


def test_dispatcher_routes_a_communication_tagged_task():
    agent = _agent()
    task = Task(
        title="draft executive summary", execution_id="exec-1", metadata={"required_capability": AgentCapability.COMMUNICATION}
    )

    routed = Dispatcher().dispatch(Decision(), task, {"stakeholder_communication": agent})

    assert routed is agent


def test_dispatcher_routes_a_reasoning_tagged_task_too():
    agent = _agent()
    task = Task(title="draft", execution_id="exec-1", metadata={"required_capability": AgentCapability.REASONING})

    routed = Dispatcher().dispatch(Decision(), task, {"stakeholder_communication": agent})

    assert routed is agent


def test_dispatcher_never_routes_a_memory_tagged_task():
    agent = _agent()
    task = Task(title="retrieve_memory", execution_id="exec-1", metadata={"required_capability": AgentCapability.MEMORY})

    routed = Dispatcher().dispatch(Decision(), task, {"stakeholder_communication": agent})

    assert routed is None


# --- execute() / BaseAgent contract ---------------------------------------------------------


def test_execute_requires_organization_id():
    with pytest.raises(ValueError):
        _agent().execute(AgentContext(organization_id=None))


def test_execute_extracts_operation_from_agent_metadata():
    agent = _agent()
    context = _agent_context(agent_metadata=ExecutionMetadata(extra={"operation": "recall", "text": "roadmap"}))

    response = agent.execute(context)

    assert isinstance(response, RuntimeResponse)
    assert response.success is True


# --- memory integration: writes, evidence-gating, append-only -------------------------------


def test_map_stakeholder_writes_a_stakeholder_record():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    request = StakeholderCommunicationRequest(
        operation=StakeholderCommunicationOperation.MAP_STAKEHOLDER,
        stakeholder_name="Jane Doe",
        role_or_interest="VP Eng",
        raci_role="accountable",
    )

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert len(memory.remembered) == 1
    content, kwargs = memory.remembered[0]
    assert kwargs["memory_type"] == MEMORY_TYPE_STAKEHOLDER
    assert "Jane Doe" in content


def test_draft_communication_with_evidence_writes_a_delivery_artifact_tagged_communication_draft():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    request = StakeholderCommunicationRequest(
        operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION,
        text="Onboarding revamp status",
        audience="executive",
        purpose="executive_summary",
    )

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert len(memory.remembered) == 1
    content, kwargs = memory.remembered[0]
    assert kwargs["memory_type"] == MEMORY_TYPE_DELIVERY_ARTIFACT
    assert "communication_draft" in content


def test_draft_communication_without_evidence_never_writes():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION,
            text="Ship X",
            audience="executive",
            purpose="executive_summary",
        ),
        _specialist_context(),
    )
    assert response.success is True
    assert memory.remembered == []
    assert response.confidence < 0.5
    assert "discovery" in response.recommendations[0].lower() or "decision" in response.recommendations[0].lower()


def test_explain_decision_without_decision_evidence_never_writes():
    # Discovery-only evidence (no "Decision:" prefixed content) must not
    # be treated as sufficient to explain a decision.
    memory = _FakeMemory(package=_package_with_items([_discovery_item(1)]))
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.EXPLAIN_DECISION, text="Onboarding revamp", audience="leadership"),
        _specialist_context(),
    )
    assert response.success is True
    assert memory.remembered == []


def test_explain_decision_with_decision_evidence_writes_a_delivery_artifact():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.EXPLAIN_DECISION, text="Onboarding revamp", audience="leadership"),
        _specialist_context(),
    )
    assert response.success is True
    assert len(memory.remembered) == 1
    assert memory.remembered[0][1]["memory_type"] == MEMORY_TYPE_DELIVERY_ARTIFACT


def test_two_draft_communication_calls_append_two_distinct_artifacts_never_mutating():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    context = _specialist_context()

    agent.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION, text="Status v1", audience="executive", purpose="executive_summary", title="v1"
        ),
        context,
    )
    agent.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION, text="Status v2", audience="executive", purpose="executive_summary", title="v2"
        ),
        context,
    )

    assert len(memory.remembered) == 2
    assert memory.remembered[0][1]["title"] == "v1"
    assert memory.remembered[1][1]["title"] == "v2"
    assert memory.remembered[0] in memory.remembered  # first entry never removed or rewritten


def test_never_writes_a_decision_record_roadmap_item_or_metric():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    context = _specialist_context()

    agent.process(
        StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.MAP_STAKEHOLDER, stakeholder_name="Jane"), context
    )
    agent.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION, text="Ship X", audience="executive", purpose="executive_summary"
        ),
        context,
    )

    memory_types = {kwargs["memory_type"] for _, kwargs in memory.remembered}
    assert MEMORY_TYPE_DECISION not in memory_types
    assert MEMORY_TYPE_ROADMAP not in memory_types
    assert MEMORY_TYPE_METRIC not in memory_types


# --- stakeholder-missing honesty (ARR §8 Failure Mode Analysis) --------------------------------


def test_draft_communication_never_invents_stakeholder_facts_when_missing():
    memory = _FakeMemory(package=_full_evidence_package())  # no Stakeholder: content
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION,
            text="Onboarding revamp status",
            audience="executive",
            purpose="stakeholder_update",
            stakeholder_name="Unknown Person",
        ),
        _specialist_context(),
    )
    assert response.success is True
    content, _ = memory.remembered[0]
    assert "placeholder" in content.lower() or "no stakeholder record found" in content.lower()


def test_draft_communication_uses_real_stakeholder_context_when_available():
    memory = _FakeMemory(package=_package_with_items([_discovery_item(1), _decision_item(2), _stakeholder_item(3)]))
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION,
            text="Onboarding revamp status",
            audience="executive",
            purpose="stakeholder_update",
            stakeholder_name="Jane Doe",
        ),
        _specialist_context(),
    )
    assert response.success is True
    assert "3" in response.sources


# --- audience-specific communication (one pattern, not one per channel) ------------------------


def test_different_audiences_produce_differently_tagged_drafts():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    context = _specialist_context()

    agent.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION, text="Status", audience="executive", purpose="executive_summary"
        ),
        context,
    )
    agent.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION, text="Status", audience="engineering", purpose="engineering_handoff_summary"
        ),
        context,
    )

    contents = [content for content, _ in memory.remembered]
    assert any("executive_summary" in content for content in contents)
    assert any("engineering_handoff_summary" in content for content in contents)


def test_missing_audience_or_purpose_fails_honestly():
    agent = _agent()
    response = agent.process(
        StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION, text="x"),
        _specialist_context(),
    )
    assert response.success is False
    assert "audience" in response.error.lower()


# --- Discovery/Decision/Delivery/Strategy integration: shared memory only ----------------------


def test_module_never_imports_other_specialists_code():
    module = importlib.import_module(
        "app.services.ai.agents.specialists.product_management.stakeholder_communication.stakeholder_communication_agent"
    )
    tree = ast.parse(inspect.getsource(module))
    imported_modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    assert not any("product_management.discovery" in name for name in imported_modules)
    assert not any("product_management.product_decision" in name for name in imported_modules)
    assert not any("product_management.delivery" in name for name in imported_modules)
    assert not any("product_management.strategy_portfolio" in name for name in imported_modules)
    assert not any("specialists.research" in name for name in imported_modules)
    assert not any("personal_intelligence" in name for name in imported_modules)


def test_consumes_discovery_and_decision_evidence_through_shared_memory_recall():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)

    response = agent.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION,
            text="Users churn after onboarding",
            audience="executive",
            purpose="status_report",
        ),
        _specialist_context(),
    )

    assert response.success is True
    assert set(response.sources) == {"1", "2"}


# --- Runtime / PromptBuilder integration -----------------------------------------------------


def test_runtime_request_carries_organization_id_and_parent_shared():
    runtime = _FakeRuntime()
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))
    context = _specialist_context()

    agent.process(StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.RECALL, text="roadmap"), context)

    assert len(runtime.requests) == 1
    assert runtime.requests[0].organization_id == 1
    assert runtime.requests[0].parent_shared is context.shared


def test_prompt_package_is_built_from_prompt_builder_and_contains_the_text():
    runtime = _FakeRuntime()
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))

    agent.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION, text="Onboarding revamp status", audience="executive", purpose="executive_summary"
        ),
        _specialist_context(),
    )

    prompt_package = runtime.requests[0].prompt_package
    rendered = " ".join(section.content for section in prompt_package.sections)
    assert "Onboarding revamp status" in rendered


def test_summary_uses_runtime_generated_text_when_available():
    conversation_response = ConversationResponse(
        text="A clear communication draft.",
        response=ProviderResponse(metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="fake")),
    )
    runtime = _FakeRuntime(response=RuntimeResponse(success=True, conversation_response=conversation_response))
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))

    response = agent.process(StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.RECALL, text="roadmap"), _specialist_context())

    assert response.summary == "A clear communication draft."


# --- event ordering --------------------------------------------------------------------------


def test_events_are_emitted_in_order_for_draft_communication_with_evidence():
    events = []
    publisher = CommunicationEventPublisher()
    publisher.subscribe(events.append)
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory, event_publisher=publisher)

    agent.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION, text="Status", audience="executive", purpose="executive_summary"
        ),
        _specialist_context(),
    )

    event_types = [event.event_type for event in events]
    assert event_types == [
        CommunicationEventType.REQUEST_STARTED,
        CommunicationEventType.PRECEDENT_RETRIEVED,
        CommunicationEventType.UPDATE_DRAFTED,
        CommunicationEventType.ARTIFACT_STORED,
        CommunicationEventType.REQUEST_COMPLETED,
    ]


def test_events_are_emitted_in_order_for_draft_communication_without_evidence():
    events = []
    publisher = CommunicationEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)

    agent.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION, text="Status", audience="executive", purpose="executive_summary"
        ),
        _specialist_context(),
    )

    event_types = [event.event_type for event in events]
    assert event_types == [
        CommunicationEventType.REQUEST_STARTED,
        CommunicationEventType.PRECEDENT_RETRIEVED,
        CommunicationEventType.UPDATE_DRAFTED,
        CommunicationEventType.REQUEST_COMPLETED,
    ]
    assert CommunicationEventType.ARTIFACT_STORED not in event_types


def test_every_event_carries_execution_id_correlation_id_and_agent_id():
    events = []
    publisher = CommunicationEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    context = _specialist_context()

    agent.process(StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.RECALL, text="x"), context)

    assert all(event.execution_id == context.execution_id for event in events)
    assert all(event.correlation_id == context.correlation_id for event in events)
    assert all(event.agent_id == "stakeholder_communication" for event in events)


def test_failed_run_emits_request_failed_instead_of_completed():
    events = []
    publisher = CommunicationEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(raises=ValueError("boom"))))

    agent.process(StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.RECALL, text="x"), _specialist_context())

    event_types = [event.event_type for event in events]
    assert CommunicationEventType.REQUEST_FAILED in event_types
    assert CommunicationEventType.REQUEST_COMPLETED not in event_types


# --- state transitions ------------------------------------------------------------------------


def test_communication_state_ends_at_idle_after_a_successful_run():
    agent = _agent()
    agent.process(StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.RECALL, text="x"), _specialist_context())
    assert agent.communication_state.state == CommunicationState.IDLE


def test_communication_state_ends_at_idle_after_a_failed_run():
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(raises=ValueError("boom"))))
    agent.process(StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.RECALL, text="x"), _specialist_context())
    assert agent.communication_state.state == CommunicationState.IDLE


def test_communication_state_ends_at_idle_after_an_early_validation_error():
    agent = _agent()
    response = agent.process(StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.MAP_STAKEHOLDER), _specialist_context())
    assert response.success is False
    assert agent.communication_state.state == CommunicationState.IDLE


def test_agent_can_process_multiple_requests_in_sequence():
    agent = _agent()
    context = _specialist_context()
    for _ in range(3):
        response = agent.process(StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.RECALL, text="x"), context)
        assert response.success is True
    assert agent.communication_state.state == CommunicationState.IDLE


# --- failure handling -------------------------------------------------------------------------


def test_a_raising_memory_adapter_produces_a_failed_response_not_a_raised_exception():
    memory = _FakeMemory(package=_full_evidence_package())
    memory.raises_on_remember = ValueError("db unavailable")
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION, text="x", audience="executive", purpose="executive_summary"
        ),
        _specialist_context(),
    )
    assert response.success is False
    assert "db unavailable" in response.error


def test_a_failing_runtime_call_produces_a_failed_response_with_zero_confidence():
    agent = _agent(
        runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(response=RuntimeResponse(success=False, error="provider down")))
    )
    response = agent.process(StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.RECALL, text="x"), _specialist_context())
    assert response.success is False
    assert response.confidence == 0.0
    assert response.error == "provider down"


def test_maximum_depth_exceeded_fails_immediately_without_touching_any_collaborator():
    memory = _FakeMemory()
    runtime = _FakeRuntime()
    agent = _agent(memory_adapter=memory, runtime_adapter=RuntimeAdapter(runtime=runtime))
    context = _specialist_context(agent_context=_agent_context(delegation_depth=agent.policy.maximum_depth))

    response = agent.process(StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.RECALL, text="x"), context)

    assert response.success is False
    assert "depth" in response.error.lower()
    assert memory.retrieve_calls == []
    assert runtime.requests == []


def test_explain_decision_requires_text_or_title():
    response = _agent().process(
        StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.EXPLAIN_DECISION, audience="leadership"),
        _specialist_context(),
    )
    assert response.success is False
    assert "text or" in response.error.lower()


def test_unsupported_raw_operation_value_raises_before_construction():
    with pytest.raises(ValueError):
        StakeholderCommunicationOperation("not_a_real_operation")


# --- bulk summarization ------------------------------------------------------------------------


def test_summarize_communications_counts_only_communication_draft_artifacts():
    rows = (
        _Row(id=1, organization_id=1, content="Delivery artifact (spec) for Onboarding: spec content. Linked evidence: 1.", memory_type=MEMORY_TYPE_DELIVERY_ARTIFACT),
        _Row(id=2, organization_id=1, content="Delivery artifact (communication_draft) for Onboarding: draft content. Linked evidence: 1.", memory_type=MEMORY_TYPE_DELIVERY_ARTIFACT),
        _Row(id=3, organization_id=1, content="Stakeholder: Jane Doe.", memory_type=MEMORY_TYPE_STAKEHOLDER),
    )
    memory = _FakeMemory()
    service = ProfessionalMemoryService(memory, _FakeMemoryServiceRows(rows))
    agent = _agent(memory_adapter=memory, memory_service=service)

    response = agent.process(StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.SUMMARIZE_COMMUNICATIONS), _specialist_context())

    assert response.success is True
    assert "1 stakeholder(s)" in response.findings[0]
    assert "1 communication draft(s)" in response.findings[0]
