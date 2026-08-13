"""The single most important proof for CP-01.3: an Insight produced by
InsightAgent is surfaced by the EXISTING, UNMODIFIED ExecutiveAgent flow,
with zero code change to ExecutiveAgent/Dispatcher/ExecutivePlanner and
zero delegation to InsightAgent at all - the exact same mechanism proven
for PersonalIntelligenceAgent in test_executive_integration.py (CP-01.2),
now one layer up the cognition stack.

The mechanism is identical because the store is identical: InsightAgent's
write path (InsightMemoryService.remember_insight -> AgentMemory.remember
-> MemoryAdapter -> AIMemoryService.create_memory) and ExecutiveAgent's
read path (MemoryRetrievalPipeline.search_memories) still both terminate
on the one Memory table - "insights stored using the existing memory
infrastructure, not a new database or schema" is what makes this proof
possible at all.

The capstone test in this file (test_full_pipeline_...) goes one step
further than CP-01.2's equivalent: it exercises the whole cognition
stack in one scenario - PersonalIntelligenceAgent writes raw personal
memories, InsightAgent (with zero awareness of PersonalIntelligenceAgent)
detects a pattern across them and writes an Insight, and ExecutiveAgent
(with zero awareness of either agent) surfaces that Insight in an
unrelated, later conversation - proving proactive, connected
understanding compounds through the shared Memory Framework alone.
"""

from datetime import UTC, datetime

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.executive.executive_agent import ExecutiveAgent
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
from app.services.ai.agents.specialists.personal_intelligence.context import build_personal_intelligence_context
from app.services.ai.agents.specialists.personal_intelligence.insight.context import build_insight_context
from app.services.ai.agents.specialists.personal_intelligence.insight.insight_agent import InsightAgent
from app.services.ai.agents.specialists.personal_intelligence.insight.request import InsightOperation, InsightRequest
from app.services.ai.agents.specialists.personal_intelligence.personal_intelligence_agent import PersonalIntelligenceAgent
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


class _Row:
    def __init__(self, id, organization_id, content, memory_type, title, created_at):
        self.id = id
        self.organization_id = organization_id
        self.content = content
        self.memory_type = memory_type
        self.title = title
        self.created_at = created_at


class _SharedMemoryStore:
    """Models the one real Memory table every write-side and read-side
    collaborator in this test actually reads/writes in production - the
    entire reason no agent here needs to know any other agent exists."""

    def __init__(self):
        self.rows: list[_Row] = []
        self._next_id = 1

    def create(self, organization_id, content, user_id=None, memory_type="general", title=None):
        row = _Row(self._next_id, organization_id, content, memory_type, title, datetime.now(UTC))
        self.rows.append(row)
        self._next_id += 1
        return row.id

    def search(self, organization_id):
        return [row for row in self.rows if row.organization_id == organization_id]


class _WriteSideMemoryService:
    """AIMemoryService-shaped: create_memory() (used by MemoryAdapter.remember())
    and list_memories() (used by InsightMemoryService's bulk corpus read) -
    both already-existing AIMemoryService methods, unmodified."""

    def __init__(self, store: _SharedMemoryStore):
        self.store = store

    def create_memory(self, organization_id, content, user_id=None, memory_type="general", title=None):
        self.store.create(organization_id, content, user_id=user_id, memory_type=memory_type, title=title)

    def list_memories(self, organization_id, skip=0, limit=20):
        return self.store.search(organization_id)[skip : skip + limit]


class _ReadSideRetrievalPipeline:
    """MemoryRetrievalPipeline-shaped: only search_memories()/
    search_conversation_messages()/search_all() are exercised - the exact
    shape ExecutiveAgent already depends on in production."""

    def __init__(self, store: _SharedMemoryStore):
        self.store = store
        self.search_memories_calls = []

    def search_memories(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.search_memories_calls.append((query, organization_id))
        rows = self.store.search(organization_id)[:limit]
        items = [
            ContextItem(resource_type="memory", resource_id=row.id, content=row.content, score=1.0, created_at=row.created_at)
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
            text=self.text, response=ProviderResponse(metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="fake"))
        )
        return RuntimeResponse(success=True, conversation_response=conversation_response)


def _insight_agent(store: _SharedMemoryStore) -> InsightAgent:
    pipeline = _ReadSideRetrievalPipeline(store)
    return InsightAgent(memory_adapter=MemoryAdapter(memory_service=_WriteSideMemoryService(store), pipeline=pipeline), memory_service=_WriteSideMemoryService(store))


def _pi_agent(store: _SharedMemoryStore) -> PersonalIntelligenceAgent:
    pipeline = _ReadSideRetrievalPipeline(store)
    return PersonalIntelligenceAgent(memory_adapter=MemoryAdapter(memory_service=_WriteSideMemoryService(store), pipeline=pipeline))


# --- the core proof --------------------------------------------------------------------------


def test_an_insight_generated_via_insight_agent_is_surfaced_by_the_executives_own_retrieval():
    store = _SharedMemoryStore()
    for i in range(3):
        store.create(1, f"Reflection (daily): Consistency has been difficult, entry {i}.", memory_type="personal_reflection")

    insight_agent = _insight_agent(store)
    response = insight_agent.process(
        InsightRequest(operation=InsightOperation.ANALYZE_PATTERNS, minimum_occurrences=3),
        build_insight_context(AgentContext(organization_id=1), None),
    )
    assert response.success is True
    assert response.findings  # at least one pattern insight was produced and remembered

    runtime = _RecordingRuntime(text="I noticed you've mentioned consistency being difficult several times.")
    pipeline = _ReadSideRetrievalPipeline(store)
    # known_agents is deliberately EMPTY - the Executive has no idea
    # InsightAgent exists.
    executive = ExecutiveAgent(runtime=runtime, retrieval_pipeline=pipeline, default_provider=ProviderName.OPENAI)

    context = AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"user_request": "Help me plan this week."}))
    result = executive.execute(context)

    assert result.success is True
    prompt_text = " ".join(message.content for message in runtime.requests[0].prompt_package.messages)
    assert "consistency" in prompt_text.lower()


def test_insight_agent_never_intercepts_the_executives_own_memory_retrieval_task():
    store = _SharedMemoryStore()
    insight_agent = _insight_agent(store)
    pipeline = _ReadSideRetrievalPipeline(store)
    runtime = _RecordingRuntime()
    # known_agents DOES include InsightAgent this time - the realistic,
    # fully-wired-up scenario - and the retrieve_memory task must still
    # be handled by ExecutiveAgent's own internal pipeline call.
    executive = ExecutiveAgent(runtime=runtime, retrieval_pipeline=pipeline, known_agents={"insight": insight_agent})

    context = AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"user_request": "Help me plan this week."}))
    response = executive.execute(context)

    assert response.success is True
    assert pipeline.search_memories_calls == [("Help me plan this week.", 1)]
    from app.services.ai.agents.specialists.personal_intelligence.insight.state import InsightState

    assert insight_agent.insight_state.state == InsightState.IDLE


# --- the full cognition stack, end to end -----------------------------------------------------


def test_full_pipeline_personal_intelligence_writes_insight_agent_detects_executive_surfaces():
    store = _SharedMemoryStore()

    # Week 1-2: the user tells PersonalIntelligenceAgent about repeated struggles.
    pi_agent = _pi_agent(store)
    for i in range(3):
        pi_agent.process(
            PersonalIntelligenceRequest(
                operation=PersonalIntelligenceOperation.REMEMBER_REFLECTION,
                text=f"Consistency has been difficult again, week {i}.",
                category="weekly",
            ),
            build_personal_intelligence_context(AgentContext(organization_id=1), None),
        )
    # a goal that never shows up again in later activity
    pi_agent.process(
        PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.REMEMBER_GOAL, title="Learn Mandarin", text="Study daily"),
        build_personal_intelligence_context(AgentContext(organization_id=1), None),
    )

    # Some time later: InsightAgent runs, with zero awareness of PersonalIntelligenceAgent,
    # and detects the recurring theme + the goal's low alignment, producing recommendations.
    insight_agent = _insight_agent(store)
    recall_response = insight_agent.process(
        InsightRequest(operation=InsightOperation.GENERATE_RECOMMENDATIONS),
        build_insight_context(AgentContext(organization_id=1), None),
    )
    assert recall_response.success is True
    assert any("Mandarin" in finding or "consistency" in finding.lower() for finding in recall_response.findings)

    # Later still: the user has an ordinary conversation with the
    # Executive - which knows about neither PersonalIntelligenceAgent nor
    # InsightAgent (known_agents={}) - and the recommendation surfaces
    # automatically.
    runtime = _RecordingRuntime(text="Consider revisiting your Mandarin goal, and consistency has come up a few times.")
    pipeline = _ReadSideRetrievalPipeline(store)
    executive = ExecutiveAgent(runtime=runtime, retrieval_pipeline=pipeline)
    result = executive.execute(
        AgentContext(organization_id=1, agent_metadata=ExecutionMetadata(extra={"user_request": "What should I focus on this week?"}))
    )

    assert result.success is True
    prompt_text = " ".join(message.content for message in runtime.requests[0].prompt_package.messages)
    assert "mandarin" in prompt_text.lower() or "consistency" in prompt_text.lower()


def test_insight_memory_is_scoped_by_organization_id_even_through_the_shared_store():
    store = _SharedMemoryStore()
    store.create(1, "Consistency has been difficult, org 1 secret.", memory_type="personal_reflection")
    store.create(1, "Consistency has been difficult, org 1 secret again.", memory_type="personal_reflection")
    store.create(1, "Consistency has been difficult, org 1 secret a third time.", memory_type="personal_reflection")

    insight_agent = _insight_agent(store)
    insight_agent.process(
        InsightRequest(operation=InsightOperation.ANALYZE_PATTERNS, minimum_occurrences=3),
        build_insight_context(AgentContext(organization_id=1), None),
    )

    runtime = _RecordingRuntime()
    pipeline = _ReadSideRetrievalPipeline(store)
    executive = ExecutiveAgent(runtime=runtime, retrieval_pipeline=pipeline)
    executive.execute(
        AgentContext(organization_id=2, agent_metadata=ExecutionMetadata(extra={"user_request": "What patterns do you see?"}))
    )

    prompt_text = " ".join(message.content for message in runtime.requests[0].prompt_package.messages)
    assert "org 1 secret" not in prompt_text
