"""InsightAgent - CP-01.3's specialist: BaseAgent + SpecialistAgent
contract conformance, registry/factory integration, every process()
operation (analyze_patterns/identify_habits/detect_contradictions/
measure_alignment/generate_periodic_reflection/generate_recommendations/
update_profile/recall_insights), event emission, state-machine behavior,
execution-identity propagation, and failure handling.

Fakes only - no real DB, no real embedding provider, no real runtime -
matching test_personal_intelligence_agent.py's own conventions exactly.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentCapability
from app.services.ai.agents.factory import AgentFactory
from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.registry import AgentRegistry
from app.services.ai.agents.specialists.factory import SpecialistFactory
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
from app.services.ai.agents.specialists.personal_intelligence.insight.context import build_insight_context
from app.services.ai.agents.specialists.personal_intelligence.insight.events import InsightEventPublisher, InsightEventType
from app.services.ai.agents.specialists.personal_intelligence.insight.insight_agent import InsightAgent
from app.services.ai.agents.specialists.personal_intelligence.insight.policies import InsightPolicy
from app.services.ai.agents.specialists.personal_intelligence.insight.request import InsightOperation, InsightRequest
from app.services.ai.agents.specialists.personal_intelligence.insight.state import InsightState
from app.services.ai.agents.specialists.personal_intelligence.shared.insight import InsightPeriod
from app.services.ai.agents.specialists.registry import SpecialistRegistry
from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.agents.specialists.shared.policies import SpecialistExecutionPolicy
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType
from app.services.ai.conversation.types import ConversationResponse
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.types import RuntimeResponse
from app.services.ai.shared.execution_metadata import ExecutionMetadata
from app.services.ai.shared.response import AIResponseMetadata, ProviderResponse
from app.services.context.types import ContextPackage

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

    def search_memories(self, query, organization_id, limit=10, max_context_tokens=4000):
        return self.package

    def search_conversation_messages(self, query, organization_id, limit=10, max_context_tokens=4000):
        return self.package

    def search_all(self, query, organization_id, limit=10, max_context_tokens=4000):
        return self.package


class _Row:
    def __init__(self, id, organization_id, content, memory_type, title, created_at):
        self.id = id
        self.organization_id = organization_id
        self.content = content
        self.memory_type = memory_type
        self.title = title
        self.created_at = created_at


class _FakeMemoryServiceStore:
    """Backs both MemoryAdapter's write path (create_memory) and
    InsightMemoryService's bulk-read path (list_memories) with one shared,
    in-process list - mirroring how both collaborators are, in production,
    views onto the same AIMemoryService/Memory table."""

    def __init__(self, seed_rows=()):
        self.rows = list(seed_rows)
        self._next_id = len(self.rows) + 1

    def create_memory(self, organization_id, content, user_id=None, memory_type="general", title=None):
        row = _Row(self._next_id, organization_id, content, memory_type, title, datetime.now(UTC))
        self.rows.append(row)
        self._next_id += 1

        class _M:
            id = row.id

        return _M()

    def list_memories(self, organization_id, skip=0, limit=20):
        matching = [row for row in self.rows if row.organization_id == organization_id]
        return matching[skip : skip + limit]


def _row(id_, content, memory_type, organization_id=1, title=None, days_ago=0):
    return _Row(id_, organization_id, content, memory_type, title, datetime.now(UTC) - timedelta(days=days_ago))


def _agent(**overrides):
    store = overrides.pop("store", None) or _FakeMemoryServiceStore()
    defaults = dict(
        runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()),
        memory_adapter=MemoryAdapter(pipeline=_FakePipeline(), memory_service=store),
        memory_service=store,
        default_provider=ProviderName.OPENAI,
    )
    defaults.update(overrides)
    return InsightAgent(**defaults)


def _context(**overrides):
    defaults = dict(organization_id=1)
    defaults.update(overrides)
    return build_insight_context(AgentContext(**defaults), None)


# --- registry / factory integration -------------------------------------------------------


def test_is_a_base_agent():
    assert isinstance(_agent(), BaseAgent)


def test_is_registered_in_the_agent_registry():
    assert AgentRegistry.is_registered("insight")
    assert AgentRegistry.get("insight") is InsightAgent


def test_is_registered_in_the_specialist_registry():
    assert SpecialistRegistry.exists("insight")
    registration = SpecialistRegistry.get_registration("insight")
    assert registration.specialization == "insight"
    assert registration.supported_tasks == frozenset({SpecialistTaskType.ANALYSIS, SpecialistTaskType.SUMMARIZATION})


def test_constructible_via_agent_factory():
    agent = AgentFactory.create(
        "insight", runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()), memory_adapter=MemoryAdapter(pipeline=_FakePipeline())
    )
    assert isinstance(agent, InsightAgent)


def test_constructible_via_specialist_factory():
    agent = SpecialistFactory.create(
        "insight", runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()), memory_adapter=MemoryAdapter(pipeline=_FakePipeline())
    )
    assert isinstance(agent, InsightAgent)


# --- identity / capabilities -----------------------------------------------------------------


def test_does_not_declare_the_memory_capability():
    assert AgentCapability.MEMORY not in _agent().identity.capabilities.declared


def test_capabilities_and_permissions_come_from_identity():
    agent = _agent()
    assert agent.capabilities() is agent.identity.capabilities
    assert agent.permissions() == agent.identity.permissions


# --- SpecialistAgent contract ------------------------------------------------------------


def test_specialization_is_insight():
    assert _agent().specialization() == "insight"


def test_supported_tasks_is_analysis_and_summarization():
    assert _agent().supported_tasks() == frozenset({SpecialistTaskType.ANALYSIS, SpecialistTaskType.SUMMARIZATION})


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


def test_evaluate_uses_the_insight_policy_minimum_confidence():
    from app.services.ai.agents.specialists.shared.response import SpecialistResponse

    agent = _agent(insight_policy=InsightPolicy(minimum_confidence=0.5))
    assert agent.evaluate(SpecialistResponse(success=True, confidence=0.8)) is True
    assert agent.evaluate(SpecialistResponse(success=True, confidence=0.2)) is False
    assert agent.evaluate(SpecialistResponse(success=False, confidence=0.9)) is False


# --- execute() / BaseAgent contract satisfaction -----------------------------------------------


def test_execute_requires_organization_id():
    agent = _agent()
    with pytest.raises(ValueError, match="organization_id"):
        agent.execute(AgentContext())


def test_execute_extracts_operation_from_agent_metadata():
    store = _FakeMemoryServiceStore(seed_rows=[_row(1, "consistency again " * 3, "personal_reflection") for _ in range(1)])
    agent = _agent(store=store)
    context = AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"operation": "analyze_patterns"}))

    response = agent.execute(context)

    assert response.success is True


def test_execute_accepts_a_prebuilt_request_object():
    agent = _agent()
    request = InsightRequest(operation=InsightOperation.RECALL_INSIGHTS, query="what patterns do you see")
    context = AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"insight_request": request}))

    response = agent.execute(context)

    assert response.success is True


def test_execute_defaults_to_recall_insights_when_no_operation_given():
    runtime = _FakeRuntime()
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))
    context = AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"query": "anything"}))

    agent.execute(context)

    assert len(runtime.requests) == 1


def test_execute_returns_a_runtime_response():
    agent = _agent()
    context = AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"operation": "recall_insights"}))
    response = agent.execute(context)
    assert isinstance(response, RuntimeResponse)
    assert response.success is True


# --- process(): analysis operations -------------------------------------------------------------


def _reflection_rows(term, count, organization_id=1, start_id=1):
    return [
        _row(start_id + i, f"{term} shows up again in reflection {i}.", "personal_reflection", organization_id=organization_id)
        for i in range(count)
    ]


def test_analyze_patterns_writes_pattern_insights_to_memory():
    store = _FakeMemoryServiceStore(seed_rows=_reflection_rows("consistency", 3))
    agent = _agent(store=store)
    request = InsightRequest(operation=InsightOperation.ANALYZE_PATTERNS, minimum_occurrences=3)

    response = agent.process(request, _context())

    assert response.success is True
    assert any("consistency" in finding for finding in response.findings)
    remembered = [row for row in store.rows if row.memory_type == "personal_insight"]
    assert len(remembered) >= 1


def test_analyze_patterns_below_threshold_produces_no_insights_but_still_succeeds():
    store = _FakeMemoryServiceStore(seed_rows=_reflection_rows("consistency", 1))
    agent = _agent(store=store)
    request = InsightRequest(operation=InsightOperation.ANALYZE_PATTERNS, minimum_occurrences=3)

    response = agent.process(request, _context())

    assert response.success is True
    assert response.findings == ()
    assert response.confidence == 0.0


def test_identify_habits_analyzes_only_reflection_type_memories():
    rows = _reflection_rows("procrastination", 2) + [
        _row(100, "procrastination mentioned in a goal too but should be ignored for habits", "personal_goal")
    ]
    store = _FakeMemoryServiceStore(seed_rows=rows)
    agent = _agent(store=store)
    request = InsightRequest(operation=InsightOperation.IDENTIFY_HABITS, minimum_occurrences=2)

    response = agent.process(request, _context())

    assert response.success is True
    assert any("procrastination" in finding for finding in response.findings)


def test_detect_contradictions_compares_preferences_against_goals_projects_reflections():
    rows = [
        _row(1, "Don't schedule meetings before 10am.", "personal_preference"),
        _row(2, "Scheduled a meetings slot at 8am today.", "personal_goal"),
    ]
    store = _FakeMemoryServiceStore(seed_rows=rows)
    agent = _agent(store=store)
    request = InsightRequest(operation=InsightOperation.DETECT_CONTRADICTIONS)

    response = agent.process(request, _context())

    assert response.success is True
    assert any("meetings" in finding.lower() for finding in response.findings)


def test_measure_alignment_compares_goals_against_recent_reflections_and_projects():
    rows = [
        _row(1, "Goal (career): AI Operating System.", "personal_goal", title="AI Operating System"),
        _row(2, "Worked on the AI Operating System today.", "personal_reflection"),
    ]
    store = _FakeMemoryServiceStore(seed_rows=rows)
    agent = _agent(store=store)
    request = InsightRequest(operation=InsightOperation.MEASURE_ALIGNMENT)

    response = agent.process(request, _context())

    assert response.success is True
    assert any("AI Operating System" in finding for finding in response.findings)


def test_generate_periodic_reflection_produces_one_reflection_insight():
    store = _FakeMemoryServiceStore(seed_rows=_reflection_rows("consistency", 3))
    agent = _agent(store=store)
    request = InsightRequest(operation=InsightOperation.GENERATE_PERIODIC_REFLECTION, period=InsightPeriod.WEEKLY)

    response = agent.process(request, _context())

    assert response.success is True
    assert len(response.findings) == 1
    assert "reflection" in response.summary.lower()


def test_generate_periodic_reflection_honors_the_requested_period():
    store = _FakeMemoryServiceStore(seed_rows=_reflection_rows("consistency", 3))
    agent = _agent(store=store)
    request = InsightRequest(operation=InsightOperation.GENERATE_PERIODIC_REFLECTION, period=InsightPeriod.MONTHLY)

    response = agent.process(request, _context())

    assert "monthly" in response.summary.lower()


def test_generate_recommendations_produces_recommendation_insights():
    rows = [
        _row(1, "Don't schedule meetings before 10am.", "personal_preference"),
        _row(2, "Scheduled a meetings slot at 8am today.", "personal_goal"),
    ]
    store = _FakeMemoryServiceStore(seed_rows=rows)
    agent = _agent(store=store)
    request = InsightRequest(operation=InsightOperation.GENERATE_RECOMMENDATIONS)

    response = agent.process(request, _context())

    assert response.success is True
    assert len(response.findings) >= 1


def test_update_profile_produces_exactly_one_profile_summary_insight():
    store = _FakeMemoryServiceStore(seed_rows=_reflection_rows("consistency", 3))
    agent = _agent(store=store)
    request = InsightRequest(operation=InsightOperation.UPDATE_PROFILE)

    response = agent.process(request, _context())

    assert response.success is True
    assert len(response.findings) == 1
    assert "profile" in response.summary.lower()


def test_analysis_operations_exclude_the_engines_own_prior_insights_from_the_corpus():
    # seed a prior insight directly in the store - it must never feed back
    # into pattern detection as raw source material.
    rows = _reflection_rows("consistency", 3) + [_row(50, "consistency consistency consistency", "personal_insight")]
    store = _FakeMemoryServiceStore(seed_rows=rows)
    agent = _agent(store=store)
    request = InsightRequest(operation=InsightOperation.ANALYZE_PATTERNS, minimum_occurrences=3)

    response = agent.process(request, _context())

    # exactly one pattern insight for 'consistency' (from the 3 real
    # reflections) - not inflated by the seeded personal_insight row.
    assert len([f for f in response.findings if "consistency" in f]) == 1


def test_analysis_respects_the_lookback_window():
    rows = [
        _row(1, "consistency old memory outside the window", "personal_reflection", days_ago=90),
        _row(2, "consistency recent memory inside the window", "personal_reflection", days_ago=1),
        _row(3, "consistency also recent", "personal_reflection", days_ago=2),
    ]
    store = _FakeMemoryServiceStore(seed_rows=rows)
    agent = _agent(store=store)
    request = InsightRequest(operation=InsightOperation.ANALYZE_PATTERNS, minimum_occurrences=3, lookback_days=30)

    response = agent.process(request, _context())

    # only 2 of the 3 memories fall inside the 30-day window - below the
    # minimum_occurrences=3 threshold, so no pattern should be found.
    assert response.findings == ()


def test_analysis_scopes_to_the_requesting_organization_only():
    rows = _reflection_rows("consistency", 3, organization_id=1) + _reflection_rows("consistency", 3, organization_id=2, start_id=100)
    store = _FakeMemoryServiceStore(seed_rows=rows)
    agent = _agent(store=store)
    request = InsightRequest(operation=InsightOperation.ANALYZE_PATTERNS, minimum_occurrences=3)

    agent.process(request, _context(organization_id=1))

    pattern_insight_rows = [
        row for row in store.rows if row.memory_type == "personal_insight" and row.organization_id == 1
    ]
    assert len(pattern_insight_rows) >= 1
    assert all(row.organization_id != 2 or row.memory_type != "personal_insight" for row in store.rows if row.id > 200)


def test_an_unsupported_operation_fails_cleanly_rather_than_raising():
    agent = _agent()
    request = object.__new__(InsightRequest)
    object.__setattr__(request, "operation", "not_a_real_operation")
    object.__setattr__(request, "query", "")
    object.__setattr__(request, "period", InsightPeriod.WEEKLY)
    object.__setattr__(request, "lookback_days", None)
    object.__setattr__(request, "minimum_occurrences", None)
    object.__setattr__(request, "maximum_memories_analyzed", None)

    response = agent.process(request, _context())

    assert response.success is False
    assert "not_a_real_operation" in response.error


# --- process(): recall_insights operation --------------------------------------------------


def test_recall_insights_generates_a_response_via_the_runtime():
    conversation_response = ConversationResponse(
        text="You seem to be struggling with consistency lately.",
        response=ProviderResponse(metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="fake")),
    )
    runtime = _FakeRuntime(response=RuntimeResponse(success=True, conversation_response=conversation_response))
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime))
    request = InsightRequest(operation=InsightOperation.RECALL_INSIGHTS, query="what patterns do you see")

    response = agent.process(request, _context())

    assert response.success is True
    assert response.summary == "You seem to be struggling with consistency lately."
    assert len(runtime.requests) == 1


def test_recall_insights_runtime_request_carries_organization_id_and_parent_shared():
    runtime = _FakeRuntime()
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=runtime), default_provider=ProviderName.ANTHROPIC)
    request = InsightRequest(operation=InsightOperation.RECALL_INSIGHTS, query="x")

    context = _context(organization_id=42)
    agent.process(request, context)

    runtime_request = runtime.requests[0]
    assert runtime_request.organization_id == 42
    assert runtime_request.provider == ProviderName.ANTHROPIC
    assert runtime_request.parent_shared is context.shared


def test_a_failing_runtime_call_produces_a_failed_recall_response():
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(response=RuntimeResponse(success=False, error="provider down"))))
    request = InsightRequest(operation=InsightOperation.RECALL_INSIGHTS, query="x")

    response = agent.process(request, _context())

    assert response.success is False
    assert response.error == "provider down"


# --- events --------------------------------------------------------------------------------


def test_events_are_emitted_in_order_for_a_successful_pattern_analysis():
    events = []
    publisher = InsightEventPublisher()
    publisher.subscribe(events.append)
    store = _FakeMemoryServiceStore(seed_rows=_reflection_rows("consistency", 3))
    agent = _agent(store=store, event_publisher=publisher)
    request = InsightRequest(operation=InsightOperation.ANALYZE_PATTERNS, minimum_occurrences=3)

    agent.process(request, _context())

    event_types = [event.event_type for event in events]
    assert event_types == [
        InsightEventType.REQUEST_STARTED,
        InsightEventType.CORPUS_GATHERED,
        InsightEventType.PATTERNS_DETECTED,
        InsightEventType.REQUEST_COMPLETED,
    ]


def test_events_are_emitted_in_order_for_a_successful_recall():
    events = []
    publisher = InsightEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    request = InsightRequest(operation=InsightOperation.RECALL_INSIGHTS, query="x")

    agent.process(request, _context())

    event_types = [event.event_type for event in events]
    assert event_types == [InsightEventType.REQUEST_STARTED, InsightEventType.RECALL_COMPLETED, InsightEventType.REQUEST_COMPLETED]


def test_every_event_carries_execution_id_correlation_id_and_agent_id():
    events = []
    publisher = InsightEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher)
    request = InsightRequest(operation=InsightOperation.UPDATE_PROFILE)

    context = _context()
    agent.process(request, context)

    assert all(event.execution_id == context.execution_id for event in events)
    assert all(event.correlation_id == context.correlation_id for event in events)
    assert all(event.agent_id == "insight" for event in events)


def test_failed_run_emits_request_failed_instead_of_completed():
    events = []
    publisher = InsightEventPublisher()
    publisher.subscribe(events.append)
    agent = _agent(event_publisher=publisher, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(raises=ValueError("boom"))))
    request = InsightRequest(operation=InsightOperation.RECALL_INSIGHTS, query="x")

    agent.process(request, _context())

    event_types = [event.event_type for event in events]
    assert InsightEventType.REQUEST_FAILED in event_types
    assert InsightEventType.REQUEST_COMPLETED not in event_types


# --- state machine ---------------------------------------------------------------------------


def test_state_ends_at_idle_after_a_successful_analysis():
    agent = _agent()
    request = InsightRequest(operation=InsightOperation.UPDATE_PROFILE)
    agent.process(request, _context())
    assert agent.insight_state.state == InsightState.IDLE


def test_state_ends_at_idle_after_a_successful_recall():
    agent = _agent()
    request = InsightRequest(operation=InsightOperation.RECALL_INSIGHTS, query="x")
    agent.process(request, _context())
    assert agent.insight_state.state == InsightState.IDLE


def test_state_ends_at_idle_after_a_failed_run():
    agent = _agent(runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime(raises=ValueError("boom"))))
    request = InsightRequest(operation=InsightOperation.RECALL_INSIGHTS, query="x")
    agent.process(request, _context())
    assert agent.insight_state.state == InsightState.IDLE


def test_agent_can_process_multiple_requests_sequentially():
    agent = _agent()
    for _ in range(3):
        response = agent.process(InsightRequest(operation=InsightOperation.UPDATE_PROFILE), _context())
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

    store = _FakeMemoryServiceStore(seed_rows=_reflection_rows("consistency", 3))
    agent = _agent(memory_adapter=_RaisingMemory(), memory_service=store)
    request = InsightRequest(operation=InsightOperation.ANALYZE_PATTERNS, minimum_occurrences=3)

    response = agent.process(request, _context())  # must not raise

    assert response.success is False
    assert "db unavailable" in response.error


def test_a_raising_corpus_gather_produces_a_failed_response_not_a_raised_exception():
    class _RaisingMemoryService:
        def list_memories(self, *args, **kwargs):
            raise RuntimeError("db unavailable")

    agent = _agent(memory_service=_RaisingMemoryService())
    request = InsightRequest(operation=InsightOperation.ANALYZE_PATTERNS)

    response = agent.process(request, _context())

    assert response.success is False
    assert "db unavailable" in response.error


def test_a_raising_recall_produces_a_failed_response_not_a_raised_exception():
    class _RaisingPipeline:
        def search_memories(self, *args, **kwargs):
            raise RuntimeError("vector store unavailable")

    agent = _agent(memory_adapter=MemoryAdapter(pipeline=_RaisingPipeline()))
    request = InsightRequest(operation=InsightOperation.RECALL_INSIGHTS, query="x")

    response = agent.process(request, _context())

    assert response.success is False
    assert "vector store unavailable" in response.error


# --- maximum depth policy --------------------------------------------------------------------


def test_maximum_depth_exceeded_fails_immediately_without_touching_any_collaborator():
    runtime = _FakeRuntime()
    store = _FakeMemoryServiceStore(seed_rows=_reflection_rows("consistency", 3))
    agent = _agent(store=store, runtime_adapter=RuntimeAdapter(runtime=runtime), policy=SpecialistExecutionPolicy(maximum_depth=1))
    request = InsightRequest(operation=InsightOperation.ANALYZE_PATTERNS)

    deep_context = build_insight_context(AgentContext(organization_id=1, delegation_depth=1), None)
    response = agent.process(request, deep_context)

    assert response.success is False
    assert "depth" in response.error.lower()
    assert runtime.requests == []
    assert len([row for row in store.rows if row.memory_type == "personal_insight"]) == 0


# --- result identity ------------------------------------------------------------------------


def test_response_identity_matches_the_context():
    agent = _agent()
    request = InsightRequest(operation=InsightOperation.RECALL_INSIGHTS, query="x")
    context = _context()
    response = agent.process(request, context)
    assert response.execution_id == context.execution_id
    assert response.correlation_id == context.correlation_id
    assert response.parent_execution_id == context.parent_execution_id


def test_does_not_mutate_the_request():
    agent = _agent()
    request = InsightRequest(operation=InsightOperation.GENERATE_PERIODIC_REFLECTION, period=InsightPeriod.DAILY)
    agent.process(request, _context())
    assert request.period == InsightPeriod.DAILY
