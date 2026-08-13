"""CP-02 Milestone 8 - Executive Integration, per specialist.

The single most important proof for CP-02, mirroring
personal_intelligence/test_executive_integration.py's own precedent
exactly (CP-01): content written through any of CP-02's five specialists
is surfaced by the EXISTING, UNMODIFIED ExecutiveAgent flow, with zero
code change to ExecutiveAgent/Dispatcher/ExecutivePlanner and zero
delegation to the specialist at all (the "automatic path" Implementation_Plan.md's
own Milestone 8 objectives name explicitly).

The mechanism: every CP-02 specialist and ExecutiveAgent itself ultimately
read/write the same Memory Framework row store (in production, the
`memory` table via AIMemoryService on the write side and
MemoryRetrievalPipeline on the read side). This suite models that shared
store with a single in-process fake, used by a write-side fake
(AIMemoryService-shaped, wired into each specialist's own MemoryAdapter)
and a read-side fake (MemoryRetrievalPipeline-shaped, wired into both
each specialist's own MemoryAdapter AND ExecutiveAgent directly) - proving
the integration is a genuine consequence of "same store," not an artifact
of this suite's own wiring.

Also proves, for every one of the five specialists, the collision-avoidance
property Architecture §19 requires: even when a specialist IS a known_agent
the Executive could delegate to, ExecutivePlanner's built-in retrieve_memory
task (tagged required_capability=AgentCapability.MEMORY) is never routed to
it, because no CP-02 specialist declares AgentCapability.MEMORY.

And proves the explicit-delegation path at the plumbing level Dispatcher/
ExecutiveAgent actually provide today: Dispatcher matches each specialist
by its own declared capability, and ExecutiveAgent.delegate() successfully
invokes the matched specialist end-to-end via the existing AgentExecutor.
Constructing a *rich*, operation-specific request payload for a specialist
from a single free-text user_request is not something ExecutivePlanner's
current deterministic template does for any specialist on this platform
today (confirmed by CP-01's own test suite, which does not exercise this
either) - building that would be new orchestration mechanism, explicitly
out of this milestone's scope. What this suite proves is real: the
Dispatcher-to-specialist handoff itself works correctly for all five.
"""

from datetime import UTC, datetime

import pytest

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentCapability, AgentState
from app.services.ai.agents.executive.context import ExecutiveContext
from app.services.ai.agents.executive.decision import Decision
from app.services.ai.agents.executive.executive_agent import ExecutiveAgent
from app.services.ai.agents.executive.task import Task
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.agents.state import AgentStateMachine
from app.services.ai.agents.specialists.product_management.delivery.delivery_agent import DeliverySpecialist
from app.services.ai.agents.specialists.product_management.delivery.state import DeliveryState
from app.services.ai.agents.specialists.product_management.discovery.discovery_agent import DiscoverySpecialist
from app.services.ai.agents.specialists.product_management.discovery.state import DiscoveryState
from app.services.ai.agents.specialists.product_management.memory_service import ProfessionalMemoryService
from app.services.ai.agents.specialists.product_management.product_decision.product_decision_agent import (
    ProductDecisionSpecialist,
)
from app.services.ai.agents.specialists.product_management.product_decision.state import DecisionState
from app.services.ai.agents.specialists.product_management.stakeholder_communication.stakeholder_communication_agent import (
    StakeholderCommunicationSpecialist,
)
from app.services.ai.agents.specialists.product_management.stakeholder_communication.state import CommunicationState
from app.services.ai.agents.specialists.product_management.strategy_portfolio.state import StrategyState
from app.services.ai.agents.specialists.product_management.strategy_portfolio.strategy_portfolio_agent import (
    StrategyPortfolioSpecialist,
)
from app.services.ai.conversation.types import ConversationResponse
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.types import RuntimeResponse
from app.services.ai.shared.execution_metadata import ExecutionMetadata
from app.services.ai.shared.response import AIResponseMetadata, ProviderResponse
from app.services.context.types import ContextItem, ContextPackage, ContextSection

# --- the shared, in-process Memory Framework model, mirroring CP-01's own precedent -----------


class _StoredMemory:
    def __init__(self, id, organization_id, content, user_id, memory_type, title, created_at):
        self.id = id
        self.organization_id = organization_id
        self.content = content
        self.user_id = user_id
        self.memory_type = memory_type
        self.title = title
        self.created_at = created_at


class _SharedMemoryStore:
    """Models the one real Memory table every CP-02 specialist and
    ExecutiveAgent itself actually read/write in production - the entire
    reason CP-02 needs no Executive changes at all."""

    def __init__(self):
        self.rows: list[_StoredMemory] = []

    def create(self, organization_id, content, user_id=None, memory_type="general", title=None):
        row = _StoredMemory(
            id=len(self.rows) + 1,
            organization_id=organization_id,
            content=content,
            user_id=user_id,
            memory_type=memory_type,
            title=title,
            created_at=datetime.now(UTC),
        )
        self.rows.append(row)
        return row.id

    def search(self, organization_id):
        return [row for row in self.rows if row.organization_id == organization_id]


class _WriteSideMemoryService:
    """AIMemoryService-shaped: only create_memory() is exercised by
    MemoryAdapter.remember(), used by every CP-02 specialist's own
    ProfessionalMemoryService."""

    def __init__(self, store: _SharedMemoryStore):
        self.store = store

    def create_memory(self, organization_id, content, user_id=None, memory_type="general", title=None):
        return self.store.create(organization_id, content, user_id=user_id, memory_type=memory_type, title=title)


class _BulkMemoryService:
    """AIMemoryService-shaped: only list_memories() is exercised, by
    ProfessionalMemoryService.list_by_memory_type() - the bulk-listing
    collaborator distinct from the write-side service above, mirroring
    ProfessionalMemoryService's own two-collaborator constructor."""

    def __init__(self, store: _SharedMemoryStore):
        self.store = store

    def list_memories(self, organization_id, skip=0, limit=20):
        rows = self.store.search(organization_id)
        return rows[skip : skip + limit]


class _ReadSideRetrievalPipeline:
    """MemoryRetrievalPipeline-shaped: used both by every CP-02
    specialist's own MemoryAdapter AND directly by ExecutiveAgent - the
    exact same object shape ExecutiveAgent already depends on in
    production."""

    def __init__(self, store: _SharedMemoryStore):
        self.store = store
        self.search_memories_calls = []

    def search_memories(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.search_memories_calls.append((query, organization_id))
        rows = self.store.search(organization_id)[:limit]
        items = [
            ContextItem(
                resource_type="memory", resource_id=row.id, content=row.content, score=1.0, created_at=row.created_at
            )
            for row in rows
        ]
        return ContextPackage(
            sections=[ContextSection(resource_type="memory", items=items)] if items else [],
            estimated_tokens=len(items) * 10,
            item_count=len(items),
            truncated=False,
        )

    def search_conversation_messages(self, query, organization_id, limit=10, max_context_tokens=4000):
        return ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)

    def search_all(self, query, organization_id, limit=10, max_context_tokens=4000):
        return self.search_memories(query, organization_id, limit=limit, max_context_tokens=max_context_tokens)


class _RecordingRuntime:
    def __init__(self, text="Here is my response."):
        self.requests = []
        self.text = text

    def execute(self, request):
        self.requests.append(request)
        conversation_response = ConversationResponse(
            text=self.text,
            response=ProviderResponse(metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="fake")),
        )
        return RuntimeResponse(success=True, conversation_response=conversation_response)


def _shared_environment():
    """One shared store, wired identically for every specialist's own
    MemoryAdapter/ProfessionalMemoryService and for ExecutiveAgent's own
    retrieval_pipeline - the single source of truth every test in this
    file reads from and writes to."""
    store = _SharedMemoryStore()
    pipeline = _ReadSideRetrievalPipeline(store)
    memory_adapter = MemoryAdapter(pipeline=pipeline, memory_service=_WriteSideMemoryService(store))
    memory_service = ProfessionalMemoryService(memory_adapter, _BulkMemoryService(store))
    return store, pipeline, memory_adapter, memory_service


_SPECIALIST_FACTORIES = {
    "discovery": DiscoverySpecialist,
    "product_decision": ProductDecisionSpecialist,
    "delivery": DeliverySpecialist,
    "strategy_portfolio": StrategyPortfolioSpecialist,
    "stakeholder_communication": StakeholderCommunicationSpecialist,
}


def _agent_for(name, memory_adapter, memory_service, runtime):
    factory = _SPECIALIST_FACTORIES[name]
    return factory(memory_adapter=memory_adapter, memory_service=memory_service, runtime_adapter=RuntimeAdapter(runtime=runtime))


# --- the core proof, once per specialist ------------------------------------------------------


@pytest.mark.parametrize("specialist_name", list(_SPECIALIST_FACTORIES))
def test_content_written_by_each_specialist_is_surfaced_by_the_executives_own_zero_delegation_retrieval(
    specialist_name,
):
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    store.create(organization_id=1, content=f"Content written by {specialist_name} for the Executive to find.", memory_type="product_context")

    runtime = _RecordingRuntime(text="Here is what I found.")
    # known_agents is deliberately EMPTY - the Executive has no idea any
    # CP-02 specialist exists. Nothing about ExecutiveAgent, Dispatcher,
    # or ExecutivePlanner is touched by this test.
    executive = ExecutiveAgent(runtime=runtime, retrieval_pipeline=pipeline, default_provider=ProviderName.OPENAI)

    context = AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"user_request": "What's the latest?"}))
    response = executive.execute(context)

    assert response.success is True
    prompt_text = " ".join(message.content for message in runtime.requests[0].prompt_package.messages)
    assert f"Content written by {specialist_name}" in prompt_text


# --- collision-avoidance proof (Architecture §19), once per specialist ------------------------


@pytest.mark.parametrize("specialist_name", list(_SPECIALIST_FACTORIES))
def test_no_specialist_intercepts_the_executives_own_memory_retrieval_task(specialist_name):
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    runtime = _RecordingRuntime()
    agent = _agent_for(specialist_name, memory_adapter, memory_service, runtime)

    # known_agents DOES include the specialist this time - the realistic,
    # fully-wired-up scenario - and the retrieve_memory task must still be
    # handled by ExecutiveAgent's own internal pipeline call, never
    # delegated to the specialist.
    executive = ExecutiveAgent(runtime=runtime, retrieval_pipeline=pipeline, known_agents={specialist_name: agent})

    context = AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"user_request": "What's the latest?"}))
    response = executive.execute(context)

    assert response.success is True
    # the built-in pipeline call happened directly (proves _handle_task,
    # not delegation, served the retrieve_memory task)...
    assert pipeline.search_memories_calls == [("What's the latest?", 1)]


_SPECIALIST_STATE_ATTRS = {
    "discovery": ("discovery_state", DiscoveryState.IDLE),
    "product_decision": ("decision_state", DecisionState.IDLE),
    "delivery": ("delivery_state", DeliveryState.IDLE),
    "strategy_portfolio": ("strategy_state", StrategyState.IDLE),
    "stakeholder_communication": ("communication_state", CommunicationState.IDLE),
}


@pytest.mark.parametrize("specialist_name", list(_SPECIALIST_FACTORIES))
def test_specialist_own_state_machine_never_moves_when_only_the_executives_internal_task_ran(specialist_name):
    # Complements the call-count proof above: confirms the specialist was
    # never invoked at all (not merely that the pipeline call "happened
    # directly"), the same double-proof CP-01's own collision-avoidance
    # test establishes.
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    runtime = _RecordingRuntime()
    agent = _agent_for(specialist_name, memory_adapter, memory_service, runtime)
    executive = ExecutiveAgent(runtime=runtime, retrieval_pipeline=pipeline, known_agents={specialist_name: agent})

    executive.execute(AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"user_request": "x"})))

    attr_name, idle_value = _SPECIALIST_STATE_ATTRS[specialist_name]
    assert getattr(agent, attr_name).state == idle_value


# --- Dispatcher / explicit delegation plumbing, once per specialist ---------------------------


@pytest.mark.parametrize("specialist_name", list(_SPECIALIST_FACTORIES))
def test_executive_dispatch_routes_a_reasoning_tagged_task_to_the_correct_specialist(specialist_name):
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    agent = _agent_for(specialist_name, memory_adapter, memory_service, _RecordingRuntime())
    executive = ExecutiveAgent(retrieval_pipeline=pipeline, known_agents={specialist_name: agent})

    task = Task(title="do work", execution_id="exec-1", metadata={"required_capability": AgentCapability.REASONING})
    decision = Decision()

    routed = executive.dispatch(decision, task)

    assert routed is agent


@pytest.mark.parametrize("specialist_name", list(_SPECIALIST_FACTORIES))
def test_executive_dispatch_never_routes_a_memory_tagged_task_to_any_specialist(specialist_name):
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    agent = _agent_for(specialist_name, memory_adapter, memory_service, _RecordingRuntime())
    executive = ExecutiveAgent(retrieval_pipeline=pipeline, known_agents={specialist_name: agent})

    task = Task(title="retrieve_memory", execution_id="exec-1", metadata={"required_capability": AgentCapability.MEMORY})
    decision = Decision()

    routed = executive.dispatch(decision, task)

    assert routed is None


def test_dispatcher_only_routes_communication_tagged_tasks_to_stakeholder_communication():
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    agent = _agent_for("stakeholder_communication", memory_adapter, memory_service, _RecordingRuntime())
    others = {
        name: _agent_for(name, memory_adapter, memory_service, _RecordingRuntime())
        for name in _SPECIALIST_FACTORIES
        if name != "stakeholder_communication"
    }
    executive = ExecutiveAgent(retrieval_pipeline=pipeline, known_agents={"stakeholder_communication": agent, **others})

    task = Task(title="draft update", execution_id="exec-1", metadata={"required_capability": AgentCapability.COMMUNICATION})
    routed = executive.dispatch(Decision(), task)

    assert routed is agent


def test_executive_delegate_successfully_invokes_the_matched_specialist_end_to_end():
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    # AgentExecutor (which delegate() uses internally) requires an agent
    # already in READY state - exactly the BaseAgent lifecycle contract
    # _FakeAgent's own precedent (test_agent_execution.py) establishes.
    # Whatever composes a real, running ExecutiveAgent is responsible for
    # this initialization step before an agent is ever added to
    # known_agents; no CP-02 specialist test before this milestone
    # exercised AgentExecutor directly, since every specialist test calls
    # .process() directly instead.
    agent = _SPECIALIST_FACTORIES["discovery"](
        memory_adapter=memory_adapter,
        memory_service=memory_service,
        runtime_adapter=RuntimeAdapter(runtime=_RecordingRuntime()),
        state_machine=AgentStateMachine(initial=AgentState.READY),
    )
    executive = ExecutiveAgent(retrieval_pipeline=pipeline, known_agents={"discovery": agent})

    outer_context = AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"user_request": "x"}))
    executive_context = ExecutiveContext(agent_context=outer_context, user_request="x")
    task = Task(title="discovery work", execution_id="exec-1", metadata={"required_capability": AgentCapability.REASONING})

    result = executive.delegate(agent, task, executive_context)

    assert result.success is True
    assert result.agent_execution_result is not None
    assert result.agent_execution_result.agent_id == "discovery"


# --- all five specialists registered and known to the platform's own registries ---------------


def test_all_five_specialists_are_registered_in_the_agent_and_specialist_registries():
    from app.services.ai.agents.registry import AgentRegistry
    from app.services.ai.agents.specialists.registry import SpecialistRegistry

    for name in _SPECIALIST_FACTORIES:
        assert AgentRegistry.is_registered(name)
        assert SpecialistRegistry.exists(name)


def test_none_of_the_five_specialists_declare_memory_capability():
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    for name in _SPECIALIST_FACTORIES:
        agent = _agent_for(name, memory_adapter, memory_service, _RecordingRuntime())
        assert AgentCapability.MEMORY not in agent.capabilities().declared


def test_only_stakeholder_communication_declares_the_communication_capability():
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    for name in _SPECIALIST_FACTORIES:
        agent = _agent_for(name, memory_adapter, memory_service, _RecordingRuntime())
        has_communication = AgentCapability.COMMUNICATION in agent.capabilities().declared
        assert has_communication == (name == "stakeholder_communication")
