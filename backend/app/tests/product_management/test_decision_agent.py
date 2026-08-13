"""ProductDecisionSpecialist (CP-02, Milestone 4) - comprehensive
coverage: framework selection, decision generation, evidence validation,
confidence scoring, trade-off reasoning, memory integration, Executive
compatibility, PromptBuilder/Runtime integration, event ordering, state
transitions, failure handling, architecture compliance, append-only
decision history, and Discovery integration (via shared memory only).

No mocks - hand-written fakes only, mirroring test_discovery_agent.py's
own conventions exactly.
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
from app.services.ai.agents.specialists.product_management.product_decision.events import (
    DecisionEventPublisher,
    DecisionEventType,
)
from app.services.ai.agents.specialists.product_management.product_decision.product_decision_agent import (
    ProductDecisionSpecialist,
)
from app.services.ai.agents.specialists.product_management.product_decision.request import (
    DecisionOperation,
    DecisionRequest,
)
from app.services.ai.agents.specialists.product_management.product_decision.state import DecisionState
from app.services.ai.agents.specialists.product_management.shared.decision_record import DecisionFramework
from app.services.ai.agents.specialists.product_management.shared.types import (
    MEMORY_TYPE_DECISION,
    MEMORY_TYPE_PM_CRAFT_RECORD,
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
    return ProductDecisionSpecialist(**defaults)


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
    assert AgentRegistry.is_registered("product_decision")
    assert AgentRegistry.get("product_decision") is ProductDecisionSpecialist


def test_is_registered_in_the_specialist_registry():
    assert SpecialistRegistry.exists("product_decision")
    registration = SpecialistRegistry.get_registration("product_decision")
    assert registration.specialization == "product_decision"
    assert registration.supported_tasks == frozenset({SpecialistTaskType.COMPARISON})


def test_constructible_via_agent_factory():
    agent = AgentFactory.create(
        "product_decision", runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()), memory_adapter=_FakeMemory()
    )
    assert isinstance(agent, ProductDecisionSpecialist)


def test_constructible_via_specialist_factory():
    agent = SpecialistFactory.create(
        "product_decision", runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()), memory_adapter=_FakeMemory()
    )
    assert isinstance(agent, ProductDecisionSpecialist)


def test_specialization_is_product_decision():
    assert _agent().specialization() == "product_decision"


def test_self_check_and_health_check_and_health_are_true_by_default():
    agent = _agent()
    assert agent.self_check() is True
    assert agent.health_check() is True
    assert agent.health() is True


def test_evaluate_uses_the_decision_policy_minimum_confidence():
    from app.services.ai.agents.specialists.product_management.product_decision.policies import DecisionPolicy
    from app.services.ai.agents.specialists.shared.response import SpecialistResponse

    agent = _agent(decision_policy=DecisionPolicy(minimum_confidence=0.5))
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


def test_dispatcher_routes_a_reasoning_tagged_task_to_product_decision_specialist():
    agent = _agent()
    task = Task(title="prioritize", execution_id="exec-1", metadata={"required_capability": AgentCapability.REASONING})

    routed = Dispatcher().dispatch(Decision(), task, {"product_decision": agent})

    assert routed is agent


def test_dispatcher_never_routes_a_memory_tagged_task():
    agent = _agent()
    task = Task(title="retrieve_memory", execution_id="exec-1", metadata={"required_capability": AgentCapability.MEMORY})

    routed = Dispatcher().dispatch(Decision(), task, {"product_decision": agent})

    assert routed is None


# --- execute() / BaseAgent contract ---------------------------------------------------------


def test_execute_requires_organization_id():
    with pytest.raises(ValueError):
        _agent().execute(AgentContext(organization_id=None))


def test_execute_extracts_operation_from_agent_metadata():
    agent = _agent()
    context = _agent_context(agent_metadata=ExecutionMetadata(extra={"operation": "recall_decision_history"}))

    response = agent.execute(context)

    assert isinstance(response, RuntimeResponse)
    assert response.success is True


# --- framework selection ---------------------------------------------------------------------


def test_apply_framework_uses_explicit_framework_when_given():
    events = []
    publisher = DecisionEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    request = DecisionRequest(operation=DecisionOperation.APPLY_FRAMEWORK, question="sunset the old API?", framework="rice")

    agent.process(request, _specialist_context())

    selected = next(e for e in events if e.event_type == DecisionEventType.FRAMEWORK_SELECTED)
    assert selected.data["framework"] == "rice"


def test_apply_framework_auto_selects_based_on_decision_shape():
    events = []
    publisher = DecisionEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    request = DecisionRequest(operation=DecisionOperation.APPLY_FRAMEWORK, question="Should we sunset this legacy feature?")

    agent.process(request, _specialist_context())

    selected = next(e for e in events if e.event_type == DecisionEventType.FRAMEWORK_SELECTED)
    assert selected.data["framework"] == DecisionFramework.SUNSET_CHECKLIST.value


def test_apply_framework_computes_a_real_rice_score_when_inputs_given():
    agent = _agent()
    request = DecisionRequest(
        operation=DecisionOperation.APPLY_FRAMEWORK,
        question="prioritize search revamp",
        framework="rice",
        reach=1000,
        impact=2,
        confidence_input=0.8,
        effort=4,
    )

    response = agent.process(request, _specialist_context())

    assert response.success is True


def test_prioritize_features_defaults_to_ice_with_two_or_fewer_options():
    events = []
    publisher = DecisionEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    request = DecisionRequest(operation=DecisionOperation.PRIORITIZE_FEATURES, question="which of these two?", options=("A", "B"))

    agent.process(request, _specialist_context())

    selected = next(e for e in events if e.event_type == DecisionEventType.FRAMEWORK_SELECTED)
    assert selected.data["framework"] == DecisionFramework.ICE.value


def test_prioritize_features_selects_rice_with_more_than_two_options():
    events = []
    publisher = DecisionEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    request = DecisionRequest(operation=DecisionOperation.PRIORITIZE_FEATURES, options=("A", "B", "C"))

    agent.process(request, _specialist_context())

    selected = next(e for e in events if e.event_type == DecisionEventType.FRAMEWORK_SELECTED)
    assert selected.data["framework"] == DecisionFramework.RICE.value


# --- decision generation / evidence validation ------------------------------------------------


def test_generate_recommendation_with_evidence_writes_a_decision_record():
    memory = _FakeMemory(package=_package_with_items([_memory_item(resource_id=42)]))
    agent = _agent(memory_adapter=memory)
    request = DecisionRequest(
        operation=DecisionOperation.GENERATE_RECOMMENDATION, question="Should we build in-house search?", title="In-house search"
    )

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert len(memory.remembered) == 2  # DecisionRecord + PMCraftRecord
    decision_content, decision_kwargs = memory.remembered[0]
    assert decision_kwargs["memory_type"] == MEMORY_TYPE_DECISION
    craft_content, craft_kwargs = memory.remembered[1]
    assert craft_kwargs["memory_type"] == MEMORY_TYPE_PM_CRAFT_RECORD


def test_generate_recommendation_cites_supporting_evidence_ids():
    memory = _FakeMemory(package=_package_with_items([_memory_item(resource_id=42), _memory_item(resource_id=43)]))
    agent = _agent(memory_adapter=memory)
    request = DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="pricing change", title="Pricing")

    response = agent.process(request, _specialist_context())

    assert set(response.sources) == {"42", "43"}
    decision_content, _ = memory.remembered[0]
    assert "42, 43" in decision_content


def test_generate_recommendation_always_carries_a_named_framework_and_counterpoint():
    memory = _FakeMemory(package=_package_with_items([_memory_item(resource_id=1)]))
    agent = _agent(memory_adapter=memory)
    request = DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="pricing change", title="Pricing")

    agent.process(request, _specialist_context())

    content, _ = memory.remembered[0]
    assert "Framework applied:" in content
    assert "Counterpoint considered:" in content


def test_generate_recommendation_with_no_evidence_never_writes_a_decision_record():
    memory = _FakeMemory()  # empty package - no evidence
    agent = _agent(memory_adapter=memory)
    request = DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="Should we build X?", title="Build X")

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert memory.remembered == []
    assert response.confidence < 0.5
    assert "discovery" in response.recommendations[0].lower()


def test_generate_recommendation_never_fabricates_certainty_when_evidence_is_thin():
    memory = _FakeMemory(package=_package_with_items([_memory_item(resource_id=1)]))
    agent = _agent(memory_adapter=memory)
    request = DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="pricing change", title="Pricing")

    response = agent.process(request, _specialist_context())

    assert response.confidence < 1.0
    content, _ = memory.remembered[0]
    assert content  # rationale/counterpoint present, never a bare "yes"


def test_generate_recommendation_honors_explicit_counterpoint_when_given():
    memory = _FakeMemory(package=_package_with_items([_memory_item(resource_id=1)]))
    agent = _agent(memory_adapter=memory)
    request = DecisionRequest(
        operation=DecisionOperation.GENERATE_RECOMMENDATION,
        question="pricing change",
        title="Pricing",
        counterpoint="Competitors may undercut this pricing",
    )

    agent.process(request, _specialist_context())

    content, _ = memory.remembered[0]
    assert "Competitors may undercut this pricing" in content


def test_generate_recommendation_records_a_pm_craft_record_referencing_the_same_decision():
    memory = _FakeMemory(package=_package_with_items([_memory_item(resource_id=1)]))
    agent = _agent(memory_adapter=memory)
    request = DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="pricing change", title="Pricing")

    agent.process(request, _specialist_context())

    craft_content, _ = memory.remembered[1]
    assert "Pricing" in craft_content


# --- confidence scoring -----------------------------------------------------------------------


def test_assess_confidence_is_low_without_evidence_and_higher_with_evidence():
    no_evidence_agent = _agent()
    low = no_evidence_agent.process(
        DecisionRequest(operation=DecisionOperation.ASSESS_CONFIDENCE, question="x"), _specialist_context()
    )

    with_evidence_agent = _agent(memory_adapter=_FakeMemory(package=_package_with_items([_memory_item()])))
    high = with_evidence_agent.process(
        DecisionRequest(operation=DecisionOperation.ASSESS_CONFIDENCE, question="x"), _specialist_context()
    )

    assert low.confidence < high.confidence


def test_assess_confidence_never_returns_a_bare_number_without_rationale():
    agent = _agent(memory_adapter=_FakeMemory(package=_package_with_items([_memory_item()])))
    response = agent.process(DecisionRequest(operation=DecisionOperation.ASSESS_CONFIDENCE, question="x"), _specialist_context())

    assert len(response.findings) == 2  # rationale + remaining_uncertainty, both always stated


# --- trade-off reasoning -----------------------------------------------------------------------


def test_analyze_tradeoffs_with_criteria_and_options():
    agent = _agent()
    request = DecisionRequest(
        operation=DecisionOperation.ANALYZE_TRADEOFFS, options=("flat pricing", "tiered pricing"), criteria=("revenue", "simplicity")
    )

    response = agent.process(request, _specialist_context())

    assert response.success is True
    assert len(response.findings) == 2
    assert all("weighed across" in finding for finding in response.findings)


def test_analyze_tradeoffs_falls_back_to_pairwise_options_without_criteria():
    agent = _agent()
    request = DecisionRequest(operation=DecisionOperation.ANALYZE_TRADEOFFS, options=("A", "B"))

    response = agent.process(request, _specialist_context())

    assert "A vs B" in response.findings


def test_compare_options_requires_at_least_two_options():
    agent = _agent()
    response = agent.process(
        DecisionRequest(operation=DecisionOperation.COMPARE_OPTIONS, options=("only-one",)), _specialist_context()
    )
    assert response.success is False
    assert "at least two" in response.error.lower()


def test_compare_options_returns_every_named_option():
    agent = _agent()
    response = agent.process(
        DecisionRequest(operation=DecisionOperation.COMPARE_OPTIONS, options=("build", "buy", "partner")),
        _specialist_context(),
    )
    assert set(response.findings) == {"build", "buy", "partner"}


# --- risk identification / assumption validation ------------------------------------------------


def test_identify_risks_always_returns_at_least_one_risk():
    agent = _agent()
    response = agent.process(DecisionRequest(operation=DecisionOperation.IDENTIFY_RISKS, question="x"), _specialist_context())
    assert response.success is True
    assert len(response.findings) >= 1


def test_identify_risks_includes_a_risk_per_stated_assumption():
    agent = _agent(memory_adapter=_FakeMemory(package=_package_with_items([_memory_item()])))
    response = agent.process(
        DecisionRequest(operation=DecisionOperation.IDENTIFY_RISKS, question="x", assumptions=("users will adopt this",)),
        _specialist_context(),
    )
    assert any("users will adopt this" in finding for finding in response.findings)


def test_validate_assumptions_requires_at_least_one_assumption():
    agent = _agent()
    response = agent.process(DecisionRequest(operation=DecisionOperation.VALIDATE_ASSUMPTIONS), _specialist_context())
    assert response.success is False
    assert "assumption" in response.error.lower()


def test_validate_assumptions_marks_unvalidated_when_no_evidence_found():
    agent = _agent()  # empty package
    response = agent.process(
        DecisionRequest(operation=DecisionOperation.VALIDATE_ASSUMPTIONS, assumptions=("users want speed",)),
        _specialist_context(),
    )
    assert "unvalidated" in response.findings[0]


def test_validate_assumptions_marks_evidence_backed_when_evidence_found():
    agent = _agent(memory_adapter=_FakeMemory(package=_package_with_items([_memory_item()])))
    response = agent.process(
        DecisionRequest(operation=DecisionOperation.VALIDATE_ASSUMPTIONS, assumptions=("users want speed",)),
        _specialist_context(),
    )
    assert "evidence-backed" in response.findings[0]


# --- memory integration: never bypasses AgentMemory ---------------------------------------------


def test_recall_decision_history_reads_via_list_by_memory_type_bulk_path():
    rows = (
        _Row(id=1, organization_id=1, content="Decision: A. Framework applied: rice.", memory_type=MEMORY_TYPE_DECISION),
        _Row(id=2, organization_id=1, content="Decision: B. Framework applied: ice.", memory_type=MEMORY_TYPE_DECISION),
    )
    memory = _FakeMemory()
    service = ProfessionalMemoryService(memory, _FakeMemoryServiceRows(rows))
    agent = _agent(memory_adapter=memory, memory_service=service)

    response = agent.process(DecisionRequest(operation=DecisionOperation.RECALL_DECISION_HISTORY), _specialist_context())

    assert response.success is True
    assert "2 decision(s)" in response.findings[0]


def test_search_is_never_called_by_operations_that_use_recall():
    memory = _FakeMemory()
    agent = _agent(memory_adapter=memory)
    agent.process(DecisionRequest(operation=DecisionOperation.ASSESS_CONFIDENCE, question="x"), _specialist_context())

    assert len(memory.retrieve_calls) == 1
    assert memory.search_calls == []


# --- append-only decision history: never mutates a prior decision -------------------------------


def test_two_generate_recommendation_calls_append_two_distinct_decision_records_never_mutating():
    memory = _FakeMemory(package=_package_with_items([_memory_item(resource_id=1)]))
    agent = _agent(memory_adapter=memory)
    context = _specialist_context()

    agent.process(
        DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="pricing v1", title="Pricing v1"), context
    )
    agent.process(
        DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="pricing v2", title="Pricing v2"), context
    )

    decision_writes = [call for call in memory.remembered if call[1]["memory_type"] == MEMORY_TYPE_DECISION]
    assert len(decision_writes) == 2
    assert decision_writes[0][1]["title"] == "Pricing v1"
    assert decision_writes[1][1]["title"] == "Pricing v2"
    # both remain in the log - the first entry is never removed or rewritten
    assert decision_writes[0] in memory.remembered


# --- Discovery integration: shared memory only, never Discovery's own types ----------------------


def test_module_never_imports_discovery_agent_code():
    module = importlib.import_module(
        "app.services.ai.agents.specialists.product_management.product_decision.product_decision_agent"
    )
    tree = ast.parse(inspect.getsource(module))
    imported_modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    assert not any("product_management.discovery" in name for name in imported_modules)


def test_module_never_imports_research_agent_or_personal_intelligence_code():
    module = importlib.import_module(
        "app.services.ai.agents.specialists.product_management.product_decision.product_decision_agent"
    )
    tree = ast.parse(inspect.getsource(module))
    imported_modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    assert not any("specialists.research" in name for name in imported_modules)
    assert not any("personal_intelligence" in name for name in imported_modules)


def test_consumes_discovery_findings_through_shared_memory_recall():
    # Discovery's own to_memory_content() rendering, exactly as
    # DiscoverySpecialist (Milestone 3) would have written it - Product
    # Decision reads it through the identical ProfessionalMemoryService
    # surface, never a private channel.
    discovery_finding_item = _memory_item(
        content="Discovery finding: Users churn after onboarding Source: Support tickets Q3. Status: unknown.",
        resource_id=99,
    )
    memory = _FakeMemory(package=_package_with_items([discovery_finding_item]))
    agent = _agent(memory_adapter=memory)

    response = agent.process(
        DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="Users churn after onboarding", title="Onboarding fix"),
        _specialist_context(),
    )

    assert response.success is True
    assert "99" in response.sources


# --- Runtime / PromptBuilder integration -----------------------------------------------------


def test_runtime_request_carries_organization_id_and_parent_shared():
    runtime = _FakeRuntime()
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))
    context = _specialist_context()

    agent.process(DecisionRequest(operation=DecisionOperation.ASSESS_CONFIDENCE, question="x"), context)

    assert len(runtime.requests) == 1
    assert runtime.requests[0].organization_id == 1
    assert runtime.requests[0].parent_shared is context.shared


def test_prompt_package_is_built_from_prompt_builder_and_contains_the_question():
    runtime = _FakeRuntime()
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))

    agent.process(
        DecisionRequest(operation=DecisionOperation.APPLY_FRAMEWORK, question="Should we build in-house search?"),
        _specialist_context(),
    )

    prompt_package = runtime.requests[0].prompt_package
    rendered = " ".join(section.content for section in prompt_package.sections)
    assert "Should we build in-house search?" in rendered


def test_summary_uses_runtime_generated_text_when_available():
    conversation_response = ConversationResponse(
        text="A clear decision framing.",
        response=ProviderResponse(metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="fake")),
    )
    runtime = _FakeRuntime(response=RuntimeResponse(success=True, conversation_response=conversation_response))
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))

    response = agent.process(DecisionRequest(operation=DecisionOperation.ASSESS_CONFIDENCE, question="x"), _specialist_context())

    assert response.summary == "A clear decision framing."


# --- event ordering --------------------------------------------------------------------------


def test_events_are_emitted_in_order_for_generate_recommendation_with_evidence():
    events = []
    publisher = DecisionEventPublisher()
    publisher.subscribe(events.append)
    memory = _FakeMemory(package=_package_with_items([_memory_item(resource_id=1)]))
    agent = _agent(memory_adapter=memory, event_publisher=publisher)

    agent.process(
        DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="x", title="Decision X"),
        _specialist_context(),
    )

    event_types = [event.event_type for event in events]
    assert event_types == [
        DecisionEventType.REQUEST_STARTED,
        DecisionEventType.PRECEDENT_RETRIEVED,
        DecisionEventType.FRAMEWORK_SELECTED,
        DecisionEventType.DECISION_GENERATED,
        DecisionEventType.DECISION_STORED,
        DecisionEventType.CRAFT_RECORD_STORED,
        DecisionEventType.REQUEST_COMPLETED,
    ]


def test_events_are_emitted_in_order_for_generate_recommendation_without_evidence():
    events = []
    publisher = DecisionEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)

    agent.process(
        DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="x", title="Decision X"),
        _specialist_context(),
    )

    event_types = [event.event_type for event in events]
    assert event_types == [
        DecisionEventType.REQUEST_STARTED,
        DecisionEventType.PRECEDENT_RETRIEVED,
        DecisionEventType.FRAMEWORK_SELECTED,
        DecisionEventType.DECISION_GENERATED,
        DecisionEventType.REQUEST_COMPLETED,
    ]
    assert DecisionEventType.DECISION_STORED not in event_types


def test_every_event_carries_execution_id_correlation_id_and_agent_id():
    events = []
    publisher = DecisionEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    context = _specialist_context()

    agent.process(DecisionRequest(operation=DecisionOperation.ASSESS_CONFIDENCE, question="x"), context)

    assert all(event.execution_id == context.execution_id for event in events)
    assert all(event.correlation_id == context.correlation_id for event in events)
    assert all(event.agent_id == "product_decision" for event in events)


def test_failed_run_emits_request_failed_instead_of_completed():
    events = []
    publisher = DecisionEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(raises=ValueError("boom"))))

    agent.process(DecisionRequest(operation=DecisionOperation.ASSESS_CONFIDENCE, question="x"), _specialist_context())

    event_types = [event.event_type for event in events]
    assert DecisionEventType.REQUEST_FAILED in event_types
    assert DecisionEventType.REQUEST_COMPLETED not in event_types


# --- state transitions ------------------------------------------------------------------------


def test_decision_state_ends_at_idle_after_a_successful_run():
    agent = _agent()
    agent.process(DecisionRequest(operation=DecisionOperation.ASSESS_CONFIDENCE, question="x"), _specialist_context())
    assert agent.decision_state.state == DecisionState.IDLE


def test_decision_state_ends_at_idle_after_a_failed_run():
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(raises=ValueError("boom"))))
    agent.process(DecisionRequest(operation=DecisionOperation.ASSESS_CONFIDENCE, question="x"), _specialist_context())
    assert agent.decision_state.state == DecisionState.IDLE


def test_decision_state_ends_at_idle_after_an_early_validation_error():
    agent = _agent()
    response = agent.process(DecisionRequest(operation=DecisionOperation.VALIDATE_ASSUMPTIONS), _specialist_context())
    assert response.success is False
    assert agent.decision_state.state == DecisionState.IDLE


def test_agent_can_process_multiple_requests_in_sequence():
    agent = _agent()
    context = _specialist_context()
    for _ in range(3):
        response = agent.process(DecisionRequest(operation=DecisionOperation.ASSESS_CONFIDENCE, question="x"), context)
        assert response.success is True
    assert agent.decision_state.state == DecisionState.IDLE


# --- failure handling -------------------------------------------------------------------------


def test_a_raising_memory_adapter_produces_a_failed_response_not_a_raised_exception():
    memory = _FakeMemory(package=_package_with_items([_memory_item(resource_id=1)]))
    memory.raises_on_remember = ValueError("db unavailable")
    agent = _agent(memory_adapter=memory)
    response = agent.process(
        DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="x", title="Decision X"),
        _specialist_context(),
    )
    assert response.success is False
    assert "db unavailable" in response.error


def test_a_failing_runtime_call_produces_a_failed_response_with_zero_confidence():
    agent = _agent(
        runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(response=RuntimeResponse(success=False, error="provider down")))
    )
    response = agent.process(DecisionRequest(operation=DecisionOperation.ASSESS_CONFIDENCE, question="x"), _specialist_context())
    assert response.success is False
    assert response.confidence == 0.0
    assert response.error == "provider down"


def test_maximum_depth_exceeded_fails_immediately_without_touching_any_collaborator():
    memory = _FakeMemory()
    runtime = _FakeRuntime()
    agent = _agent(memory_adapter=memory, runtime_adapter=RuntimeAdapter(runtime=runtime))
    context = _specialist_context(agent_context=_agent_context(delegation_depth=agent.policy.maximum_depth))

    response = agent.process(DecisionRequest(operation=DecisionOperation.ASSESS_CONFIDENCE, question="x"), context)

    assert response.success is False
    assert "depth" in response.error.lower()
    assert memory.retrieve_calls == []
    assert runtime.requests == []


def test_summarize_decision_requires_a_title_or_question():
    agent = _agent()
    response = agent.process(DecisionRequest(operation=DecisionOperation.SUMMARIZE_DECISION), _specialist_context())
    assert response.success is False
    assert "title or question" in response.error.lower()


def test_unsupported_raw_operation_value_raises_before_construction():
    with pytest.raises(ValueError):
        DecisionOperation("not_a_real_operation")
