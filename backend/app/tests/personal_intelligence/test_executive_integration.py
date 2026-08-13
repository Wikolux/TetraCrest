"""The single most important proof for CP-01: content written through
PersonalIntelligenceAgent is surfaced by the EXISTING, UNMODIFIED
ExecutiveAgent flow, with zero code change to ExecutiveAgent/Dispatcher/
ExecutivePlanner and zero delegation to PersonalIntelligenceAgent at all.

The mechanism: both agents ultimately read/write the same Memory
Framework row store (in production, the `memory` table via AIMemoryService
on the write side and MemoryRetrievalPipeline on the read side). This test
models that shared store with a single in-process fake dict, used by a
write-side fake (AIMemoryService-shaped) and a read-side fake
(MemoryRetrievalPipeline-shaped) - proving the integration is a genuine
consequence of "same store", not an artifact of the test's own wiring.

Also proves the collision-avoidance property Architecture.md §7 documents:
even when PersonalIntelligenceAgent IS a known_agent the Executive could
delegate to, ExecutivePlanner's built-in retrieve_memory task (tagged
required_capability=AgentCapability.MEMORY) is never routed to it, because
PersonalIntelligenceAgent deliberately does not declare AgentCapability.MEMORY.
"""

from datetime import UTC, datetime

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.executive.executive_agent import ExecutiveAgent
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
from app.services.ai.agents.specialists.personal_intelligence.context import build_personal_intelligence_context
from app.services.ai.agents.specialists.personal_intelligence.personal_intelligence_agent import (
    PersonalIntelligenceAgent,
)
from app.services.ai.agents.specialists.personal_intelligence.shared.goal import GoalCategory
from app.services.ai.agents.specialists.personal_intelligence.shared.request import (
    PersonalIntelligenceOperation,
    PersonalIntelligenceRequest,
)
from app.services.ai.conversation.types import ConversationResponse
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.types import RuntimeResponse
from app.services.ai.shared.execution_metadata import ExecutionMetadata
from app.services.ai.shared.response import AIResponseMetadata, ProviderResponse
from app.services.context.types import ContextItem, ContextPackage, ContextSection

# --- the shared, in-process Memory Framework model -------------------------------------------


class _SharedMemoryStore:
    """Models the one real Memory table both the write side
    (AIMemoryService) and read side (MemoryRetrievalPipeline) actually
    read/write in production - the entire reason CP-01 needs no Executive
    changes at all."""

    def __init__(self):
        self.rows = []

    def create(self, organization_id, content, user_id=None, memory_type="general", title=None):
        row_id = len(self.rows) + 1
        self.rows.append(
            dict(id=row_id, organization_id=organization_id, content=content, user_id=user_id, memory_type=memory_type, title=title)
        )
        return row_id

    def search(self, organization_id):
        return [row for row in self.rows if row["organization_id"] == organization_id]


class _WriteSideMemoryService:
    """AIMemoryService-shaped: only create_memory() is exercised by
    MemoryAdapter.remember(), used here by PersonalIntelligenceAgent."""

    def __init__(self, store: _SharedMemoryStore):
        self.store = store

    def create_memory(self, organization_id, content, user_id=None, memory_type="general", title=None):
        self.store.create(organization_id, content, user_id=user_id, memory_type=memory_type, title=title)


class _ReadSideRetrievalPipeline:
    """MemoryRetrievalPipeline-shaped: only search_memories()/
    search_conversation_messages()/search_all() are exercised, used here
    directly by ExecutiveAgent - the exact same object shape
    ExecutiveAgent already depends on in production."""

    def __init__(self, store: _SharedMemoryStore):
        self.store = store
        self.search_memories_calls = []

    def search_memories(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.search_memories_calls.append((query, organization_id))
        rows = self.store.search(organization_id)[:limit]
        items = [
            ContextItem(
                resource_type="memory", resource_id=row["id"], content=row["content"], score=1.0, created_at=datetime.now(UTC)
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


def _remember(agent, operation, **fields):
    request = PersonalIntelligenceRequest(operation=operation, **fields)
    context = build_personal_intelligence_context(AgentContext(organization_id=1), None)
    response = agent.process(request, context)
    assert response.success is True
    return response


# --- the core proof --------------------------------------------------------------------------


def test_a_goal_remembered_via_personal_intelligence_is_surfaced_by_the_executives_own_retrieval():
    store = _SharedMemoryStore()
    pipeline = _ReadSideRetrievalPipeline(store)

    pi_agent = PersonalIntelligenceAgent(memory_adapter=MemoryAdapter(memory_service=_WriteSideMemoryService(store), pipeline=pipeline))
    _remember(
        pi_agent,
        PersonalIntelligenceOperation.REMEMBER_GOAL,
        title="AI Operating System",
        text="Build a frozen, extensible AI OS architecture",
        category=GoalCategory.CAREER,
    )

    runtime = _RecordingRuntime(text="I remembered you're focused on the AI Operating System.")
    # known_agents is deliberately EMPTY - the Executive has no idea
    # PersonalIntelligenceAgent exists. Nothing about ExecutiveAgent,
    # Dispatcher, or ExecutivePlanner is touched by this test.
    executive = ExecutiveAgent(runtime=runtime, retrieval_pipeline=pipeline, default_provider=ProviderName.OPENAI)

    context = AgentContext(
        organization_id=1, agent_metadata=ExecutionMetadata(extra={"user_request": "Help me plan this week."})
    )
    response = executive.execute(context)

    assert response.success is True
    assert pipeline.search_memories_calls == [("Help me plan this week.", 1)]

    runtime_request = runtime.requests[0]
    prompt_text = " ".join(message.content for message in runtime_request.prompt_package.messages)
    assert "AI Operating System" in prompt_text
    assert "Build a frozen, extensible AI OS architecture" in prompt_text


def test_multiple_remembered_facts_all_surface_in_the_same_executive_turn():
    store = _SharedMemoryStore()
    pipeline = _ReadSideRetrievalPipeline(store)
    pi_agent = PersonalIntelligenceAgent(memory_adapter=MemoryAdapter(memory_service=_WriteSideMemoryService(store), pipeline=pipeline))

    _remember(pi_agent, PersonalIntelligenceOperation.REMEMBER_GOAL, title="AI Operating System", text="Ship it")
    _remember(pi_agent, PersonalIntelligenceOperation.REMEMBER_GOAL, title="International Product Management", text="Grow the team")
    _remember(pi_agent, PersonalIntelligenceOperation.REMEMBER_PREFERENCE, text="Consistency has been difficult lately.", category="reflection")

    runtime = _RecordingRuntime()
    executive = ExecutiveAgent(runtime=runtime, retrieval_pipeline=pipeline)
    context = AgentContext(
        organization_id=1, agent_metadata=ExecutionMetadata(extra={"user_request": "Help me plan this week."})
    )
    executive.execute(context)

    prompt_text = " ".join(message.content for message in runtime.requests[0].prompt_package.messages)
    assert "AI Operating System" in prompt_text
    assert "International Product Management" in prompt_text
    assert "Consistency has been difficult lately." in prompt_text


def test_memory_is_scoped_by_organization_id_even_through_the_shared_store():
    store = _SharedMemoryStore()
    pipeline = _ReadSideRetrievalPipeline(store)
    pi_agent = PersonalIntelligenceAgent(memory_adapter=MemoryAdapter(memory_service=_WriteSideMemoryService(store), pipeline=pipeline))

    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.REMEMBER_GOAL, title="Org 1's secret goal", text="x")
    org_1_context = build_personal_intelligence_context(AgentContext(organization_id=1), None)
    pi_agent.process(request, org_1_context)

    runtime = _RecordingRuntime()
    executive = ExecutiveAgent(runtime=runtime, retrieval_pipeline=pipeline)
    other_org_context = AgentContext(
        organization_id=2, agent_metadata=ExecutionMetadata(extra={"user_request": "What are my goals?"})
    )
    executive.execute(other_org_context)

    prompt_text = " ".join(message.content for message in runtime.requests[0].prompt_package.messages)
    assert "Org 1's secret goal" not in prompt_text


# --- collision-avoidance proof (Architecture.md §7) -----------------------------------------


def test_personal_intelligence_agent_never_intercepts_the_executives_own_memory_retrieval_task():
    store = _SharedMemoryStore()
    pipeline = _ReadSideRetrievalPipeline(store)
    pi_agent = PersonalIntelligenceAgent(memory_adapter=MemoryAdapter(memory_service=_WriteSideMemoryService(store), pipeline=pipeline))

    runtime = _RecordingRuntime()
    # known_agents DOES include PersonalIntelligenceAgent this time - the
    # realistic, fully-wired-up scenario - and the retrieve_memory task
    # must still be handled by ExecutiveAgent's own internal pipeline call,
    # never delegated to pi_agent.
    executive = ExecutiveAgent(runtime=runtime, retrieval_pipeline=pipeline, known_agents={"personal_intelligence": pi_agent})

    context = AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"user_request": "Help me plan this week."}))
    response = executive.execute(context)

    assert response.success is True
    # the built-in pipeline call happened directly (proves _handle_task,
    # not delegation, served the retrieve_memory task)...
    assert pipeline.search_memories_calls == [("Help me plan this week.", 1)]
    # ...and PersonalIntelligenceAgent's own state machine never moved -
    # proof it was never invoked at all.
    from app.services.ai.agents.specialists.personal_intelligence.state import PersonalIntelligenceState

    assert pi_agent.personal_intelligence_state.state == PersonalIntelligenceState.IDLE


def test_dispatcher_would_have_matched_a_memory_capable_agent_if_one_were_registered():
    # Sanity check on the collision risk itself: confirms the Dispatcher
    # DOES match on AgentCapability.MEMORY (so the risk PersonalIntelligenceAgent
    # avoids is real, not hypothetical), using a minimal fake agent that
    # DOES declare the capability.
    from app.services.ai.agents.base_agent import BaseAgent
    from app.services.ai.agents.capabilities import AgentCapabilities
    from app.services.ai.agents.enums import AgentCapability
    from app.services.ai.agents.executive.dispatcher import Dispatcher
    from app.services.ai.agents.executive.decision import Decision
    from app.services.ai.agents.executive.task import Task

    class _MemoryCapableAgent(BaseAgent):
        def initialize(self):
            return None

        def execute(self, context):
            raise NotImplementedError

        def pause(self):
            return None

        def resume(self):
            return None

        def cancel(self):
            return None

        def shutdown(self):
            return None

        def health(self):
            return True

        def capabilities(self):
            return AgentCapabilities(declared=frozenset({AgentCapability.MEMORY}))

        def permissions(self):
            return ()

        def memory(self):
            return None

        def planner(self):
            return None

        def runtime(self):
            return None

    from app.services.ai.agents.types import AgentIdentity

    agent = _MemoryCapableAgent(
        AgentIdentity(agent_id="memory-capable", name="memory-capable", display_name="Memory Capable")
    )
    decision = Decision(reason="x", confidence=1.0, requires_memory=True)
    task = Task(title="Retrieve memory", execution_id="exec-1", metadata={"required_capability": AgentCapability.MEMORY})

    matched = Dispatcher().dispatch(decision, task, {"memory-capable": agent})

    assert matched is agent


# --- full conversation-shaped flow ------------------------------------------------------------


def test_full_flow_remember_goal_project_and_preference_then_recall_through_the_executive():
    store = _SharedMemoryStore()
    pipeline = _ReadSideRetrievalPipeline(store)
    pi_agent = PersonalIntelligenceAgent(memory_adapter=MemoryAdapter(memory_service=_WriteSideMemoryService(store), pipeline=pipeline))

    _remember(pi_agent, PersonalIntelligenceOperation.REMEMBER_GOAL, title="AI Operating System", text="Ship it", category=GoalCategory.CAREER)
    _remember(pi_agent, PersonalIntelligenceOperation.REMEMBER_PROJECT, title="Website", text="Relaunch the marketing site")
    _remember(pi_agent, PersonalIntelligenceOperation.REMEMBER_PREFERENCE, text="I prefer strategic explanations.", category="communication")

    runtime_response_text = (
        "I remembered you're currently focused on:\n"
        "- AI Operating System\n"
        "- Website\n"
        "Would you like us to prioritize progress on those goals first?"
    )
    runtime = _RecordingRuntime(text=runtime_response_text)
    executive = ExecutiveAgent(runtime=runtime, retrieval_pipeline=pipeline)

    response = executive.execute(
        AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"user_request": "Help me plan this week."}))
    )

    assert response.success is True
    assert response.conversation_response.text == runtime_response_text

    prompt_text = " ".join(message.content for message in runtime.requests[0].prompt_package.messages)
    assert "AI Operating System" in prompt_text
    assert "Website" in prompt_text
    assert "I prefer strategic explanations." in prompt_text
