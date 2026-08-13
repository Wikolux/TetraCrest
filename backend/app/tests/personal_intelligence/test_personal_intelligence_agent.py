"""PersonalIntelligenceAgent - the CP-01 specialist itself: BaseAgent +
SpecialistAgent contract conformance, registry/factory integration, every
process() operation (remember_identity/remember_goal/update_goal_progress/
remember_project/remember_reflection/remember_preference/recall), event
emission, state-machine behavior, execution-identity propagation, and
failure handling.

Fakes only - no real DB, no real embedding provider, no real runtime -
matching test_research_agent.py's own conventions exactly.
"""

from datetime import UTC, datetime

import pytest

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentCapability
from app.services.ai.agents.factory import AgentFactory
from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.registry import AgentRegistry
from app.services.ai.agents.specialists.factory import SpecialistFactory
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
from app.services.ai.agents.specialists.personal_intelligence.context import build_personal_intelligence_context
from app.services.ai.agents.specialists.personal_intelligence.events import (
    PersonalIntelligenceEventPublisher,
    PersonalIntelligenceEventType,
)
from app.services.ai.agents.specialists.personal_intelligence.personal_intelligence_agent import (
    PersonalIntelligenceAgent,
)
from app.services.ai.agents.specialists.personal_intelligence.policies import PersonalIntelligencePolicy
from app.services.ai.agents.specialists.personal_intelligence.shared.goal import GoalStatus
from app.services.ai.agents.specialists.personal_intelligence.shared.request import (
    PersonalIntelligenceOperation,
    PersonalIntelligenceRequest,
)
from app.services.ai.agents.specialists.personal_intelligence.shared.types import (
    MEMORY_TYPE_GOAL,
    MEMORY_TYPE_IDENTITY,
    MEMORY_TYPE_PREFERENCE,
    MEMORY_TYPE_PROJECT,
    MEMORY_TYPE_REFLECTION,
)
from app.services.ai.agents.specialists.registry import SpecialistRegistry
from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.agents.specialists.shared.policies import SpecialistExecutionPolicy
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType
from app.services.ai.conversation.types import ConversationResponse
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.types import RuntimeResponse
from app.services.ai.shared.execution_metadata import ExecutionMetadata
from app.services.ai.shared.response import AIResponseMetadata, ProviderResponse
from app.services.context.types import ContextItem, ContextPackage, ContextSection

# --- fakes ---------------------------------------------------------------------------------


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

    def search_memories(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.memory_calls.append((query, organization_id))
        return self.package

    def search_conversation_messages(self, query, organization_id, limit=10, max_context_tokens=4000):
        return self.package

    def search_all(self, query, organization_id, limit=10, max_context_tokens=4000):
        return self.package


class _FakeMemoryServiceStore:
    """A minimal AIMemoryService-shaped fake: create_memory()/delete_memory().
    Used directly by MemoryAdapter(memory_service=...) so remember()/forget()
    are exercised without ever touching a real DB."""

    def __init__(self):
        self.created = []

    def create_memory(self, organization_id, content, user_id=None, memory_type="general", title=None):
        self.created.append(
            dict(organization_id=organization_id, content=content, user_id=user_id, memory_type=memory_type, title=title)
        )

        class _Row:
            id = len(self.created)

        return _Row()


def _agent(**overrides):
    defaults = dict(
        runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()),
        memory_adapter=MemoryAdapter(pipeline=_FakePipeline(), memory_service=_FakeMemoryServiceStore()),
        default_provider=ProviderName.OPENAI,
    )
    defaults.update(overrides)
    return PersonalIntelligenceAgent(**defaults)


def _context(**overrides):
    defaults = dict(organization_id=1)
    defaults.update(overrides)
    return build_personal_intelligence_context(AgentContext(**defaults), None)


# --- registry / factory integration -------------------------------------------------------


def test_is_a_base_agent():
    assert isinstance(_agent(), BaseAgent)


def test_is_registered_in_the_agent_registry():
    assert AgentRegistry.is_registered("personal_intelligence")
    assert AgentRegistry.get("personal_intelligence") is PersonalIntelligenceAgent


def test_is_registered_in_the_specialist_registry():
    assert SpecialistRegistry.exists("personal_intelligence")
    registration = SpecialistRegistry.get_registration("personal_intelligence")
    assert registration.specialization == "personal_intelligence"
    assert registration.supported_tasks == frozenset({SpecialistTaskType.UNKNOWN})


def test_constructible_via_agent_factory():
    agent = AgentFactory.create(
        "personal_intelligence",
        runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()),
        memory_adapter=MemoryAdapter(pipeline=_FakePipeline()),
    )
    assert isinstance(agent, PersonalIntelligenceAgent)


def test_constructible_via_specialist_factory():
    agent = SpecialistFactory.create(
        "personal_intelligence",
        runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()),
        memory_adapter=MemoryAdapter(pipeline=_FakePipeline()),
    )
    assert isinstance(agent, PersonalIntelligenceAgent)


# --- identity / capabilities -----------------------------------------------------------------


def test_does_not_declare_the_memory_capability():
    # Deliberate: declaring AgentCapability.MEMORY would let Dispatcher
    # route the Executive's own built-in retrieve_memory/
    # retrieve_conversations tasks to this agent, whose SpecialistResponse
    # shape is incompatible with what those tasks expect back. See
    # Architecture.md §7 and this module's own docstring.
    assert AgentCapability.MEMORY not in _agent().identity.capabilities.declared


def test_capabilities_and_permissions_come_from_identity():
    agent = _agent()
    assert agent.capabilities() is agent.identity.capabilities
    assert agent.permissions() == agent.identity.permissions


# --- SpecialistAgent contract ------------------------------------------------------------


def test_specialization_is_personal_intelligence():
    assert _agent().specialization() == "personal_intelligence"


def test_supported_tasks_is_unknown_only():
    assert _agent().supported_tasks() == frozenset({SpecialistTaskType.UNKNOWN})


def test_plan_delegates_to_the_coordinators_planner():
    agent = _agent()
    plan = agent.plan(_context())
    expected = agent.coordinator.planner.plan(_context())
    assert [(t.task_type, t.title) for t in plan] == [(t.task_type, t.title) for t in expected]


def test_planner_accessor_returns_the_coordinators_planner():
    agent = _agent()
    assert agent.planner() is agent.coordinator.planner


def test_runtime_accessor_returns_the_adapters_runtime():
    runtime = _FakeRuntime()
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))
    assert agent.runtime() is runtime


def test_memory_accessor_returns_the_agents_memory_adapter():
    agent = _agent()
    memory = agent.memory()
    assert memory is agent.coordinator.memory_adapter
    assert isinstance(memory, AgentMemory)


def test_self_check_and_health_check_and_health_are_true_by_default():
    agent = _agent()
    assert agent.self_check() is True
    assert agent.health_check() is True
    assert agent.health() is True


def test_evaluate_uses_the_personal_intelligence_policy_minimum_confidence():
    from app.services.ai.agents.specialists.shared.response import SpecialistResponse

    agent = _agent(personal_intelligence_policy=PersonalIntelligencePolicy(minimum_confidence=0.5))
    assert agent.evaluate(SpecialistResponse(success=True, confidence=0.8)) is True
    assert agent.evaluate(SpecialistResponse(success=True, confidence=0.2)) is False
    assert agent.evaluate(SpecialistResponse(success=False, confidence=0.9)) is False


# --- execute() / BaseAgent contract satisfaction -----------------------------------------------


def test_execute_requires_organization_id():
    agent = _agent()
    with pytest.raises(ValueError, match="organization_id"):
        agent.execute(AgentContext())


def test_execute_extracts_operation_and_fields_from_agent_metadata():
    store = _FakeMemoryServiceStore()
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=_FakePipeline(), memory_service=store))
    context = AgentContext(
        organization_id=1,
        agent_metadata=ExecutionMetadata(
            extra={"operation": "remember_preference", "text": "I prefer concise answers.", "category": "communication"}
        ),
    )

    response = agent.execute(context)

    assert response.success is True
    assert store.created[0]["memory_type"] == MEMORY_TYPE_PREFERENCE


def test_execute_accepts_a_prebuilt_request_object():
    store = _FakeMemoryServiceStore()
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=_FakePipeline(), memory_service=store))
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.REMEMBER_PROJECT, title="AI OS", text="Build it")
    context = AgentContext(
        organization_id=1, agent_metadata=ExecutionMetadata(extra={"personal_intelligence_request": request})
    )

    response = agent.execute(context)

    assert response.success is True
    assert store.created[0]["memory_type"] == MEMORY_TYPE_PROJECT


def test_execute_defaults_to_recall_when_no_operation_given():
    pipeline = _FakePipeline()
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=pipeline))
    context = AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"text": "what do you know about me"}))

    agent.execute(context)

    assert pipeline.memory_calls == [("what do you know about me", 1)]


def test_execute_returns_a_runtime_response():
    agent = _agent()
    context = AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"operation": "recall", "text": "x"}))
    response = agent.execute(context)
    assert isinstance(response, RuntimeResponse)
    assert response.success is True


# --- process(): remember_* operations -----------------------------------------------------------


def test_remember_identity_writes_an_identity_typed_memory():
    store = _FakeMemoryServiceStore()
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=_FakePipeline(), memory_service=store))
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.REMEMBER_IDENTITY, title="timezone", text="America/Los_Angeles")

    response = agent.process(request, _context())

    assert response.success is True
    assert "timezone" in response.summary
    assert store.created[0]["memory_type"] == MEMORY_TYPE_IDENTITY
    assert "America/Los_Angeles" in store.created[0]["content"]


def test_remember_goal_writes_a_goal_typed_memory():
    store = _FakeMemoryServiceStore()
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=_FakePipeline(), memory_service=store))
    request = PersonalIntelligenceRequest(
        operation=PersonalIntelligenceOperation.REMEMBER_GOAL, title="Ship CP-01", text="Deliver the pack", priority=1
    )

    response = agent.process(request, _context())

    assert response.success is True
    assert store.created[0]["memory_type"] == MEMORY_TYPE_GOAL
    assert store.created[0]["title"] == "Ship CP-01"


def test_update_goal_progress_writes_a_progress_note_as_a_new_memory():
    store = _FakeMemoryServiceStore()
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=_FakePipeline(), memory_service=store))
    request = PersonalIntelligenceRequest(
        operation=PersonalIntelligenceOperation.UPDATE_GOAL_PROGRESS,
        title="Ship CP-01",
        text="Finished the agent",
        progress=60.0,
        status=GoalStatus.ACTIVE.value,
    )

    response = agent.process(request, _context())

    assert response.success is True
    assert store.created[0]["memory_type"] == MEMORY_TYPE_GOAL
    assert "Progress: Ship CP-01" == store.created[0]["title"]
    assert "60%" in store.created[0]["content"]


def test_remember_project_writes_a_project_typed_memory():
    store = _FakeMemoryServiceStore()
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=_FakePipeline(), memory_service=store))
    request = PersonalIntelligenceRequest(
        operation=PersonalIntelligenceOperation.REMEMBER_PROJECT,
        title="AI Operating System",
        text="Build a frozen architecture",
        milestones=("M13", "M20.7"),
    )

    response = agent.process(request, _context())

    assert response.success is True
    assert store.created[0]["memory_type"] == MEMORY_TYPE_PROJECT
    assert "M13" in store.created[0]["content"]


def test_remember_reflection_writes_a_reflection_typed_memory():
    store = _FakeMemoryServiceStore()
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=_FakePipeline(), memory_service=store))
    request = PersonalIntelligenceRequest(
        operation=PersonalIntelligenceOperation.REMEMBER_REFLECTION, text="Today went well.", category="daily"
    )

    response = agent.process(request, _context())

    assert response.success is True
    assert store.created[0]["memory_type"] == MEMORY_TYPE_REFLECTION
    assert "Today went well." in store.created[0]["content"]


def test_remember_reflection_defaults_to_ad_hoc_period_without_a_category():
    store = _FakeMemoryServiceStore()
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=_FakePipeline(), memory_service=store))
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.REMEMBER_REFLECTION, text="x")

    agent.process(request, _context())

    assert "ad_hoc" in store.created[0]["content"]


def test_remember_preference_writes_a_preference_typed_memory():
    store = _FakeMemoryServiceStore()
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=_FakePipeline(), memory_service=store))
    request = PersonalIntelligenceRequest(
        operation=PersonalIntelligenceOperation.REMEMBER_PREFERENCE, text="I prefer concise answers.", category="communication"
    )

    response = agent.process(request, _context())

    assert response.success is True
    assert store.created[0]["memory_type"] == MEMORY_TYPE_PREFERENCE


def test_remember_writes_organization_id_and_user_id_from_context():
    store = _FakeMemoryServiceStore()
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=_FakePipeline(), memory_service=store))
    from app.services.ai.shared.execution_context import SharedExecutionContext

    context = build_personal_intelligence_context(
        AgentContext(organization_id=42, shared=SharedExecutionContext(organization_id=42, user_id=9)), None
    )
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.REMEMBER_PREFERENCE, text="x")

    agent.process(request, context)

    assert store.created[0]["organization_id"] == 42
    assert store.created[0]["user_id"] == 9


# --- process(): recall operation -----------------------------------------------------------


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


def test_recall_retrieves_from_the_memories_scope():
    pipeline = _FakePipeline(package=_memory_package([_memory_item("The user's timezone is: PST.")]))
    agent = _agent(memory_adapter=MemoryAdapter(pipeline=pipeline))
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.RECALL, text="what is my timezone")

    agent.process(request, _context())

    assert pipeline.memory_calls == [("what is my timezone", 1)]


def test_recall_generates_a_response_via_the_runtime():
    conversation_response = ConversationResponse(
        text="Your timezone is PST.",
        response=ProviderResponse(metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="fake")),
    )
    runtime = _FakeRuntime(response=RuntimeResponse(success=True, conversation_response=conversation_response))
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.RECALL, text="what is my timezone")

    response = agent.process(request, _context())

    assert response.success is True
    assert response.summary == "Your timezone is PST."
    assert len(runtime.requests) == 1


def test_recall_runtime_request_carries_organization_id_and_parent_shared():
    runtime = _FakeRuntime()
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime), default_provider=ProviderName.ANTHROPIC)
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.RECALL, text="x")

    context = _context(organization_id=42)
    agent.process(request, context)

    runtime_request = runtime.requests[0]
    assert runtime_request.organization_id == 42
    assert runtime_request.provider == ProviderName.ANTHROPIC
    assert runtime_request.parent_shared is context.shared


def test_a_failing_runtime_call_produces_a_failed_recall_response():
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(response=RuntimeResponse(success=False, error="provider down"))))
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.RECALL, text="x")

    response = agent.process(request, _context())

    assert response.success is False
    assert response.error == "provider down"


# --- unsupported operation ------------------------------------------------------------------


def test_an_unsupported_operation_fails_cleanly_rather_than_raising():
    agent = _agent()
    request = object.__new__(PersonalIntelligenceRequest)
    object.__setattr__(request, "operation", "not_a_real_operation")
    object.__setattr__(request, "text", "")
    object.__setattr__(request, "title", "")
    object.__setattr__(request, "category", "")
    object.__setattr__(request, "priority", 0)
    object.__setattr__(request, "progress", None)
    object.__setattr__(request, "status", "")
    object.__setattr__(request, "milestones", ())
    object.__setattr__(request, "lessons", ())

    response = agent.process(request, _context())

    assert response.success is False
    assert "not_a_real_operation" in response.error


# --- events --------------------------------------------------------------------------------


def test_events_are_emitted_in_order_for_a_successful_remember():
    events = []
    publisher = PersonalIntelligenceEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.REMEMBER_PREFERENCE, text="x")

    agent.process(request, _context())

    event_types = [event.event_type for event in events]
    assert event_types == [
        PersonalIntelligenceEventType.REQUEST_STARTED,
        PersonalIntelligenceEventType.PREFERENCE_REMEMBERED,
        PersonalIntelligenceEventType.REQUEST_COMPLETED,
    ]


def test_events_are_emitted_in_order_for_a_successful_recall():
    events = []
    publisher = PersonalIntelligenceEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.RECALL, text="x")

    agent.process(request, _context())

    event_types = [event.event_type for event in events]
    assert event_types == [
        PersonalIntelligenceEventType.REQUEST_STARTED,
        PersonalIntelligenceEventType.RECALL_COMPLETED,
        PersonalIntelligenceEventType.REQUEST_COMPLETED,
    ]


def test_every_event_carries_execution_id_correlation_id_and_agent_id():
    events = []
    publisher = PersonalIntelligenceEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.REMEMBER_GOAL, title="x", text="x")

    context = _context()
    agent.process(request, context)

    assert all(event.execution_id == context.execution_id for event in events)
    assert all(event.correlation_id == context.correlation_id for event in events)
    assert all(event.agent_id == "personal_intelligence" for event in events)


def test_failed_run_emits_request_failed_instead_of_completed():
    events = []
    publisher = PersonalIntelligenceEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(
        event_publisher=publisher, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(raises=ValueError("boom")))
    )
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.RECALL, text="x")

    agent.process(request, _context())

    event_types = [event.event_type for event in events]
    assert PersonalIntelligenceEventType.REQUEST_FAILED in event_types
    assert PersonalIntelligenceEventType.REQUEST_COMPLETED not in event_types


# --- state machine ---------------------------------------------------------------------------


def test_state_ends_at_idle_after_a_successful_remember():
    agent = _agent()
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.REMEMBER_PREFERENCE, text="x")

    agent.process(request, _context())

    from app.services.ai.agents.specialists.personal_intelligence.state import PersonalIntelligenceState

    assert agent.personal_intelligence_state.state == PersonalIntelligenceState.IDLE


def test_state_ends_at_idle_after_a_successful_recall():
    agent = _agent()
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.RECALL, text="x")

    agent.process(request, _context())

    from app.services.ai.agents.specialists.personal_intelligence.state import PersonalIntelligenceState

    assert agent.personal_intelligence_state.state == PersonalIntelligenceState.IDLE


def test_state_ends_at_idle_after_a_failed_run():
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(raises=ValueError("boom"))))
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.RECALL, text="x")

    agent.process(request, _context())

    from app.services.ai.agents.specialists.personal_intelligence.state import PersonalIntelligenceState

    assert agent.personal_intelligence_state.state == PersonalIntelligenceState.IDLE


def test_agent_can_process_multiple_requests_sequentially():
    # proves the state machine returning to IDLE each time actually
    # allows the next request through, not just that the field looks right.
    agent = _agent()
    for _ in range(3):
        response = agent.process(
            PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.REMEMBER_PREFERENCE, text="x"),
            _context(),
        )
        assert response.success is True


# --- failure handling -----------------------------------------------------------------------


def test_a_raising_memory_write_produces_a_failed_response_not_a_raised_exception():
    class _RaisingMemory(AgentMemory):
        def remember(self, item, **kwargs):
            raise RuntimeError("db unavailable")

        def retrieve(self, query, **kwargs):
            raise NotImplementedError

        def forget(self, item_id):
            raise NotImplementedError

        def search(self, query, **kwargs):
            raise NotImplementedError

    agent = _agent(memory_adapter=_RaisingMemory())
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.REMEMBER_PREFERENCE, text="x")

    response = agent.process(request, _context())  # must not raise

    assert response.success is False
    assert "db unavailable" in response.error


def test_a_raising_recall_produces_a_failed_response_not_a_raised_exception():
    class _RaisingPipeline:
        def search_memories(self, *args, **kwargs):
            raise RuntimeError("vector store unavailable")

    agent = _agent(memory_adapter=MemoryAdapter(pipeline=_RaisingPipeline()))
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.RECALL, text="x")

    response = agent.process(request, _context())

    assert response.success is False
    assert "vector store unavailable" in response.error


# --- maximum depth policy --------------------------------------------------------------------


def test_maximum_depth_exceeded_fails_immediately_without_touching_any_collaborator():
    runtime = _FakeRuntime()
    pipeline = _FakePipeline()
    agent = _agent(
        runtime_adapter=RuntimeAdapter(runtime=runtime),
        memory_adapter=MemoryAdapter(pipeline=pipeline),
        policy=SpecialistExecutionPolicy(maximum_depth=1),
    )
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.RECALL, text="x")

    deep_context = build_personal_intelligence_context(AgentContext(organization_id=1, delegation_depth=1), None)
    response = agent.process(request, deep_context)

    assert response.success is False
    assert "depth" in response.error.lower()
    assert runtime.requests == []
    assert pipeline.memory_calls == []


# --- result identity ------------------------------------------------------------------------


def test_response_identity_matches_the_context():
    agent = _agent()
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.RECALL, text="x")

    context = _context()
    response = agent.process(request, context)

    assert response.execution_id == context.execution_id
    assert response.correlation_id == context.correlation_id
    assert response.parent_execution_id == context.parent_execution_id


def test_does_not_mutate_the_request():
    agent = _agent()
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.REMEMBER_GOAL, title="x", text="y")

    agent.process(request, _context())

    assert request.title == "x"
    assert request.text == "y"
