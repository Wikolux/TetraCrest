"""DeliverySpecialist (CP-02, Milestone 5) - comprehensive coverage:
framework-appropriate operation behavior, memory integration (writes,
evidence-gating, append-only), Executive compatibility, PromptBuilder/
Runtime integration, event ordering, state transitions, failure handling,
architecture compliance, and Discovery/Decision integration through
shared memory only.

No mocks - hand-written fakes only, mirroring test_discovery_agent.py's/
test_decision_agent.py's own conventions exactly.
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
from app.services.ai.agents.specialists.product_management.delivery.delivery_agent import DeliverySpecialist
from app.services.ai.agents.specialists.product_management.delivery.events import (
    DeliveryEventPublisher,
    DeliveryEventType,
)
from app.services.ai.agents.specialists.product_management.delivery.request import DeliveryOperation, DeliveryRequest
from app.services.ai.agents.specialists.product_management.delivery.state import DeliveryState
from app.services.ai.agents.specialists.product_management.memory_service import ProfessionalMemoryService
from app.services.ai.agents.specialists.product_management.shared.delivery_artifact import DeliveryArtifactType
from app.services.ai.agents.specialists.product_management.shared.types import (
    MEMORY_TYPE_DELIVERY_ARTIFACT,
    MEMORY_TYPE_FEATURE,
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
    return DeliverySpecialist(**defaults)


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
    assert AgentRegistry.is_registered("delivery")
    assert AgentRegistry.get("delivery") is DeliverySpecialist


def test_is_registered_in_the_specialist_registry():
    assert SpecialistRegistry.exists("delivery")
    registration = SpecialistRegistry.get_registration("delivery")
    assert registration.specialization == "delivery"
    assert registration.supported_tasks == frozenset({SpecialistTaskType.SUMMARIZATION})


def test_constructible_via_agent_factory():
    agent = AgentFactory.create(
        "delivery", runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()), memory_adapter=_FakeMemory()
    )
    assert isinstance(agent, DeliverySpecialist)


def test_constructible_via_specialist_factory():
    agent = SpecialistFactory.create(
        "delivery", runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()), memory_adapter=_FakeMemory()
    )
    assert isinstance(agent, DeliverySpecialist)


def test_specialization_is_delivery():
    assert _agent().specialization() == "delivery"


def test_self_check_and_health_check_and_health_are_true_by_default():
    agent = _agent()
    assert agent.self_check() is True
    assert agent.health_check() is True
    assert agent.health() is True


def test_evaluate_uses_the_delivery_policy_minimum_confidence():
    from app.services.ai.agents.specialists.product_management.delivery.policies import DeliveryPolicy
    from app.services.ai.agents.specialists.shared.response import SpecialistResponse

    agent = _agent(delivery_policy=DeliveryPolicy(minimum_confidence=0.5))
    assert agent.evaluate(SpecialistResponse(success=True, confidence=0.6)) is True
    assert agent.evaluate(SpecialistResponse(success=True, confidence=0.4)) is False


# --- capability declaration / Executive collision-avoidance -------------------------------


def test_declares_only_reasoning_and_planning():
    assert _agent().capabilities().declared == frozenset({AgentCapability.REASONING, AgentCapability.PLANNING})


def test_never_declares_memory_capability():
    assert AgentCapability.MEMORY not in _agent().capabilities().declared


def test_never_declares_research_capability():
    assert AgentCapability.RESEARCH not in _agent().capabilities().declared


# --- Executive / Dispatcher compatibility --------------------------------------------------


def test_dispatcher_routes_a_reasoning_tagged_task_to_delivery_specialist():
    agent = _agent()
    task = Task(title="plan sprint", execution_id="exec-1", metadata={"required_capability": AgentCapability.REASONING})

    routed = Dispatcher().dispatch(Decision(), task, {"delivery": agent})

    assert routed is agent


def test_dispatcher_never_routes_a_memory_tagged_task():
    agent = _agent()
    task = Task(title="retrieve_memory", execution_id="exec-1", metadata={"required_capability": AgentCapability.MEMORY})

    routed = Dispatcher().dispatch(Decision(), task, {"delivery": agent})

    assert routed is None


# --- execute() / BaseAgent contract ---------------------------------------------------------


def test_execute_requires_organization_id():
    with pytest.raises(ValueError):
        _agent().execute(AgentContext(organization_id=None))


def test_execute_extracts_operation_from_agent_metadata():
    agent = _agent()
    context = _agent_context(agent_metadata=ExecutionMetadata(extra={"operation": "recall", "text": "onboarding"}))

    response = agent.execute(context)

    assert isinstance(response, RuntimeResponse)
    assert response.success is True


# --- memory integration: writes, evidence-gating, append-only -------------------------------


def test_generate_acceptance_criteria_with_evidence_writes_a_delivery_artifact():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    request = DeliveryRequest(
        operation=DeliveryOperation.GENERATE_ACCEPTANCE_CRITERIA, text="Users churn after onboarding", feature_title="Onboarding revamp"
    )

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert len(memory.remembered) == 1
    content, kwargs = memory.remembered[0]
    assert kwargs["memory_type"] == MEMORY_TYPE_DELIVERY_ARTIFACT
    assert "Onboarding revamp" in content


def test_generate_acceptance_criteria_without_evidence_never_writes():
    memory = _FakeMemory()  # empty package
    agent = _agent(memory_adapter=memory)
    request = DeliveryRequest(operation=DeliveryOperation.GENERATE_ACCEPTANCE_CRITERIA, text="Users churn", feature_title="X")

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert memory.remembered == []
    assert response.confidence < 0.5
    assert "discovery" in response.recommendations[0].lower() or "decision" in response.recommendations[0].lower()


def test_generate_recommendation_with_evidence_writes_artifact_and_feature_when_stage_given():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    request = DeliveryRequest(
        operation=DeliveryOperation.GENERATE_RECOMMENDATION,
        text="Ship onboarding revamp",
        title="Onboarding revamp",
        stage="delivery",
    )

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert len(memory.remembered) == 2
    artifact_content, artifact_kwargs = memory.remembered[0]
    assert artifact_kwargs["memory_type"] == MEMORY_TYPE_DELIVERY_ARTIFACT
    feature_content, feature_kwargs = memory.remembered[1]
    assert feature_kwargs["memory_type"] == MEMORY_TYPE_FEATURE
    assert "delivery" in feature_content


def test_generate_recommendation_without_stage_never_writes_a_feature():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    request = DeliveryRequest(operation=DeliveryOperation.GENERATE_RECOMMENDATION, text="Ship X", title="X")

    agent.process(request, _specialist_context())

    memory_types = [kwargs["memory_type"] for _, kwargs in memory.remembered]
    assert MEMORY_TYPE_FEATURE not in memory_types


def test_generate_recommendation_without_evidence_never_writes_anything():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    request = DeliveryRequest(operation=DeliveryOperation.GENERATE_RECOMMENDATION, text="Ship X", title="X", stage="delivery")

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert memory.remembered == []
    assert response.confidence == 0.0


def test_support_engineering_handoff_without_evidence_never_writes():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        DeliveryRequest(operation=DeliveryOperation.SUPPORT_ENGINEERING_HANDOFF, text="onboarding", feature_title="X"),
        _specialist_context(),
    )
    assert response.success is True
    assert memory.remembered == []


def test_decompose_story_with_evidence_writes_a_user_story_delivery_artifact():
    """Milestone 10 hardening fix: DeliveryArtifactType.USER_STORY was
    declared at Milestone 5 but never constructed anywhere until this
    milestone closed the gap the Production Readiness Report found."""
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    request = DeliveryRequest(
        operation=DeliveryOperation.DECOMPOSE_STORY, text="Users churn after onboarding", feature_title="Onboarding revamp"
    )

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert len(memory.remembered) == 1
    content, kwargs = memory.remembered[0]
    assert kwargs["memory_type"] == MEMORY_TYPE_DELIVERY_ARTIFACT
    assert f"({DeliveryArtifactType.USER_STORY.value})" in content
    assert "Onboarding revamp" in content


def test_decompose_story_without_evidence_never_writes():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    request = DeliveryRequest(operation=DeliveryOperation.DECOMPOSE_STORY, text="Users churn", feature_title="X")

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert memory.remembered == []


def test_breakdown_epic_with_evidence_writes_a_spec_delivery_artifact():
    """Milestone 10 hardening fix: DeliveryArtifactType.SPEC was declared
    at Milestone 5 but never constructed anywhere until this milestone.
    BREAKDOWN_EPIC is this specialist's closest fit to PRD §16's "PRD/spec
    drafting" capability - no operation is dedicated to spec drafting
    alone, so an epic breakdown (a structured plan for a larger unit of
    work) is the spec-shaped artifact this pack produces."""
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    request = DeliveryRequest(operation=DeliveryOperation.BREAKDOWN_EPIC, title="Onboarding overhaul", feature_title="Onboarding revamp")

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert len(memory.remembered) == 1
    content, kwargs = memory.remembered[0]
    assert kwargs["memory_type"] == MEMORY_TYPE_DELIVERY_ARTIFACT
    assert f"({DeliveryArtifactType.SPEC.value})" in content
    assert "Onboarding revamp" in content


def test_breakdown_epic_without_evidence_never_writes():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    request = DeliveryRequest(operation=DeliveryOperation.BREAKDOWN_EPIC, title="Onboarding overhaul")

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert memory.remembered == []


def test_check_launch_readiness_with_evidence_writes_a_launch_readiness_delivery_artifact():
    """Milestone 10 hardening fix: DeliveryArtifactType.LAUNCH_READINESS
    was declared at Milestone 5 but never constructed anywhere until this
    milestone closed the gap the Production Readiness Report found."""
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    request = DeliveryRequest(
        operation=DeliveryOperation.CHECK_LAUNCH_READINESS,
        text="onboarding revamp",
        items=("AC1",),
        dependencies=("auth",),
    )

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert len(memory.remembered) == 1
    content, kwargs = memory.remembered[0]
    assert kwargs["memory_type"] == MEMORY_TYPE_DELIVERY_ARTIFACT
    assert f"({DeliveryArtifactType.LAUNCH_READINESS.value})" in content


def test_check_launch_readiness_without_evidence_never_writes():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    request = DeliveryRequest(operation=DeliveryOperation.CHECK_LAUNCH_READINESS, text="onboarding revamp")

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert memory.remembered == []


def test_two_generate_recommendation_calls_append_two_distinct_artifacts_never_mutating():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    context = _specialist_context()

    agent.process(DeliveryRequest(operation=DeliveryOperation.GENERATE_RECOMMENDATION, text="Ship v1", title="v1"), context)
    agent.process(DeliveryRequest(operation=DeliveryOperation.GENERATE_RECOMMENDATION, text="Ship v2", title="v2"), context)

    artifact_writes = [call for call in memory.remembered if call[1]["memory_type"] == MEMORY_TYPE_DELIVERY_ARTIFACT]
    assert len(artifact_writes) == 2
    assert artifact_writes[0][1]["title"] == "v1"
    assert artifact_writes[1][1]["title"] == "v2"
    assert artifact_writes[0] in memory.remembered  # first entry never removed or rewritten


def test_support_retrospective_writes_artifact_only_when_evidence_exists():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        DeliveryRequest(operation=DeliveryOperation.SUPPORT_RETROSPECTIVE, text="Sprint 12", planned=("a", "b"), actual=("a",)),
        _specialist_context(),
    )
    assert response.success is True
    assert len(memory.remembered) == 1
    assert memory.remembered[0][1]["memory_type"] == MEMORY_TYPE_DELIVERY_ARTIFACT


def test_support_retrospective_never_writes_without_evidence():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        DeliveryRequest(operation=DeliveryOperation.SUPPORT_RETROSPECTIVE, text="Sprint 12", planned=("a", "b"), actual=("a",)),
        _specialist_context(),
    )
    assert response.success is True
    assert memory.remembered == []


# --- Delivery Confidence Score ------------------------------------------------------------------


def test_generate_recommendation_confidence_score_reflects_all_four_factors_when_fully_grounded():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    request = DeliveryRequest(
        operation=DeliveryOperation.GENERATE_RECOMMENDATION,
        text="Ship X",
        title="X",
        items=("AC1",),
        dependencies=("auth",),
    )

    response = agent.process(request, _specialist_context())

    assert response.confidence == 1.0  # 4/4 factors satisfied


def test_generate_recommendation_confidence_score_reflects_partial_evidence():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    request = DeliveryRequest(operation=DeliveryOperation.GENERATE_RECOMMENDATION, text="Ship X", title="X")

    response = agent.process(request, _specialist_context())

    assert response.confidence == 0.5  # Discovery + Decision satisfied, dependencies/AC missing


def test_check_launch_readiness_reports_missing_factors_by_name():
    memory = _FakeMemory(package=_package_with_items([_discovery_item(1)]))
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        DeliveryRequest(operation=DeliveryOperation.CHECK_LAUNCH_READINESS, text="onboarding revamp"), _specialist_context()
    )
    assert "Decision approved" in response.recommendations[0]
    assert "not ready" in response.recommendations[0].lower()


def test_check_launch_readiness_reports_ready_when_all_factors_satisfied():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        DeliveryRequest(
            operation=DeliveryOperation.CHECK_LAUNCH_READINESS, text="onboarding revamp", items=("AC1",), dependencies=("auth",)
        ),
        _specialist_context(),
    )
    assert "ready to launch" in response.recommendations[0].lower()
    assert "not ready" not in response.recommendations[0].lower()


# --- PM-facing scope boundary: never re-prioritizes, never invents capacity -----------------


def test_refine_backlog_requires_at_least_one_item():
    response = _agent().process(DeliveryRequest(operation=DeliveryOperation.REFINE_BACKLOG), _specialist_context())
    assert response.success is False
    assert "backlog item" in response.error.lower()


def test_refine_backlog_assesses_readiness_never_reorders_by_priority():
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        DeliveryRequest(operation=DeliveryOperation.REFINE_BACKLOG, items=("story A", "story B")), _specialist_context()
    )
    # Same order as supplied - no re-prioritization/re-ordering performed.
    assert response.findings[0].startswith("story A")
    assert response.findings[1].startswith("story B")


def test_plan_sprint_never_invents_capacity_when_not_supplied():
    agent = _agent()
    response = agent.process(
        DeliveryRequest(operation=DeliveryOperation.PLAN_SPRINT, text="Ship X"), _specialist_context()
    )
    assert "not supplied" in response.findings[1]


def test_plan_sprint_honestly_flags_overcommitment_when_capacity_supplied():
    agent = _agent()
    response = agent.process(
        DeliveryRequest(operation=DeliveryOperation.PLAN_SPRINT, text="Ship X", capacity=10, planned_load=15),
        _specialist_context(),
    )
    assert "exceeds" in response.findings[1]
    assert "descoping" in response.findings[1]


# --- Discovery/Decision integration: shared memory only, never their own types ----------------


def test_module_never_imports_discovery_or_decision_agent_code():
    module = importlib.import_module("app.services.ai.agents.specialists.product_management.delivery.delivery_agent")
    tree = ast.parse(inspect.getsource(module))
    imported_modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    assert not any("product_management.discovery" in name for name in imported_modules)
    assert not any("product_management.product_decision" in name for name in imported_modules)


def test_module_never_imports_research_agent_or_personal_intelligence_code():
    module = importlib.import_module("app.services.ai.agents.specialists.product_management.delivery.delivery_agent")
    tree = ast.parse(inspect.getsource(module))
    imported_modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    assert not any("specialists.research" in name for name in imported_modules)
    assert not any("personal_intelligence" in name for name in imported_modules)


def test_consumes_discovery_and_decision_evidence_through_shared_memory_recall():
    # Discovery's and Decision's own to_memory_content() renderings, exactly
    # as those specialists would have written them - Delivery reads both
    # through the identical ProfessionalMemoryService surface, never a
    # private channel.
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory)

    response = agent.process(
        DeliveryRequest(operation=DeliveryOperation.GENERATE_RECOMMENDATION, text="Users churn after onboarding", title="Onboarding fix"),
        _specialist_context(),
    )

    assert response.success is True
    assert set(response.sources) == {"1", "2"}


# --- Runtime / PromptBuilder integration -----------------------------------------------------


def test_runtime_request_carries_organization_id_and_parent_shared():
    runtime = _FakeRuntime()
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))
    context = _specialist_context()

    agent.process(DeliveryRequest(operation=DeliveryOperation.RECALL, text="onboarding"), context)

    assert len(runtime.requests) == 1
    assert runtime.requests[0].organization_id == 1
    assert runtime.requests[0].parent_shared is context.shared


def test_prompt_package_is_built_from_prompt_builder_and_contains_the_text():
    runtime = _FakeRuntime()
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))

    agent.process(
        DeliveryRequest(operation=DeliveryOperation.DECOMPOSE_STORY, text="Users churn after onboarding"), _specialist_context()
    )

    prompt_package = runtime.requests[0].prompt_package
    rendered = " ".join(section.content for section in prompt_package.sections)
    assert "Users churn after onboarding" in rendered


def test_summary_uses_runtime_generated_text_when_available():
    conversation_response = ConversationResponse(
        text="A clear delivery framing.",
        response=ProviderResponse(metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="fake")),
    )
    runtime = _FakeRuntime(response=RuntimeResponse(success=True, conversation_response=conversation_response))
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))

    response = agent.process(DeliveryRequest(operation=DeliveryOperation.RECALL, text="onboarding"), _specialist_context())

    assert response.summary == "A clear delivery framing."


# --- event ordering --------------------------------------------------------------------------


def test_events_are_emitted_in_order_for_generate_recommendation_with_evidence():
    events = []
    publisher = DeliveryEventPublisher()
    publisher.subscribe(events.append)
    memory = _FakeMemory(package=_full_evidence_package())
    agent = _agent(memory_adapter=memory, event_publisher=publisher)

    agent.process(
        DeliveryRequest(operation=DeliveryOperation.GENERATE_RECOMMENDATION, text="Ship X", title="X", stage="delivery"),
        _specialist_context(),
    )

    event_types = [event.event_type for event in events]
    assert event_types == [
        DeliveryEventType.REQUEST_STARTED,
        DeliveryEventType.PRECEDENT_RETRIEVED,
        DeliveryEventType.CONFIDENCE_SCORED,
        DeliveryEventType.RECOMMENDATION_GENERATED,
        DeliveryEventType.ARTIFACT_STORED,
        DeliveryEventType.FEATURE_STAGE_UPDATED,
        DeliveryEventType.REQUEST_COMPLETED,
    ]


def test_events_are_emitted_in_order_for_generate_recommendation_without_evidence():
    events = []
    publisher = DeliveryEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)

    agent.process(
        DeliveryRequest(operation=DeliveryOperation.GENERATE_RECOMMENDATION, text="Ship X", title="X"), _specialist_context()
    )

    event_types = [event.event_type for event in events]
    assert event_types == [
        DeliveryEventType.REQUEST_STARTED,
        DeliveryEventType.PRECEDENT_RETRIEVED,
        DeliveryEventType.CONFIDENCE_SCORED,
        DeliveryEventType.RECOMMENDATION_GENERATED,
        DeliveryEventType.REQUEST_COMPLETED,
    ]
    assert DeliveryEventType.ARTIFACT_STORED not in event_types
    assert DeliveryEventType.FEATURE_STAGE_UPDATED not in event_types


def test_every_event_carries_execution_id_correlation_id_and_agent_id():
    events = []
    publisher = DeliveryEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    context = _specialist_context()

    agent.process(DeliveryRequest(operation=DeliveryOperation.RECALL, text="x"), context)

    assert all(event.execution_id == context.execution_id for event in events)
    assert all(event.correlation_id == context.correlation_id for event in events)
    assert all(event.agent_id == "delivery" for event in events)


def test_failed_run_emits_request_failed_instead_of_completed():
    events = []
    publisher = DeliveryEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(raises=ValueError("boom"))))

    agent.process(DeliveryRequest(operation=DeliveryOperation.RECALL, text="x"), _specialist_context())

    event_types = [event.event_type for event in events]
    assert DeliveryEventType.REQUEST_FAILED in event_types
    assert DeliveryEventType.REQUEST_COMPLETED not in event_types


# --- state transitions ------------------------------------------------------------------------


def test_delivery_state_ends_at_idle_after_a_successful_run():
    agent = _agent()
    agent.process(DeliveryRequest(operation=DeliveryOperation.RECALL, text="x"), _specialist_context())
    assert agent.delivery_state.state == DeliveryState.IDLE


def test_delivery_state_ends_at_idle_after_a_failed_run():
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(raises=ValueError("boom"))))
    agent.process(DeliveryRequest(operation=DeliveryOperation.RECALL, text="x"), _specialist_context())
    assert agent.delivery_state.state == DeliveryState.IDLE


def test_delivery_state_ends_at_idle_after_an_early_validation_error():
    agent = _agent()
    response = agent.process(DeliveryRequest(operation=DeliveryOperation.ANALYZE_DEPENDENCIES), _specialist_context())
    assert response.success is False
    assert agent.delivery_state.state == DeliveryState.IDLE


def test_agent_can_process_multiple_requests_in_sequence():
    agent = _agent()
    context = _specialist_context()
    for _ in range(3):
        response = agent.process(DeliveryRequest(operation=DeliveryOperation.RECALL, text="x"), context)
        assert response.success is True
    assert agent.delivery_state.state == DeliveryState.IDLE


# --- failure handling -------------------------------------------------------------------------


def test_a_raising_memory_adapter_produces_a_failed_response_not_a_raised_exception():
    memory = _FakeMemory(package=_full_evidence_package())
    memory.raises_on_remember = ValueError("db unavailable")
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        DeliveryRequest(operation=DeliveryOperation.GENERATE_RECOMMENDATION, text="x", title="X"), _specialist_context()
    )
    assert response.success is False
    assert "db unavailable" in response.error


def test_a_failing_runtime_call_produces_a_failed_response_with_zero_confidence():
    agent = _agent(
        runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(response=RuntimeResponse(success=False, error="provider down")))
    )
    response = agent.process(DeliveryRequest(operation=DeliveryOperation.RECALL, text="x"), _specialist_context())
    assert response.success is False
    assert response.confidence == 0.0
    assert response.error == "provider down"


def test_maximum_depth_exceeded_fails_immediately_without_touching_any_collaborator():
    memory = _FakeMemory()
    runtime = _FakeRuntime()
    agent = _agent(memory_adapter=memory, runtime_adapter=RuntimeAdapter(runtime=runtime))
    context = _specialist_context(agent_context=_agent_context(delegation_depth=agent.policy.maximum_depth))

    response = agent.process(DeliveryRequest(operation=DeliveryOperation.RECALL, text="x"), context)

    assert response.success is False
    assert "depth" in response.error.lower()
    assert memory.retrieve_calls == []
    assert runtime.requests == []


def test_breakdown_epic_requires_a_title_or_text():
    response = _agent().process(DeliveryRequest(operation=DeliveryOperation.BREAKDOWN_EPIC), _specialist_context())
    assert response.success is False
    assert "title or text" in response.error.lower()


def test_unsupported_raw_operation_value_raises_before_construction():
    with pytest.raises(ValueError):
        DeliveryOperation("not_a_real_operation")
