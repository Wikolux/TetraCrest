"""InsightMemoryService - the Insight Engine's own thin memory wrapper,
mirroring PersonalMemoryService's "thin adapter, zero new logic" role
exactly, but serving a genuinely different access pattern.

Two memory operations, both reused, never duplicated:

1. Writing/recalling Insights themselves goes through AgentMemory
   (remember()/retrieve()) - identical to how PersonalMemoryService
   writes/recalls every other CP-01 domain object. An Insight is just
   another Memory row.

2. Gathering the raw corpus to *analyze* (pattern/habit/contradiction/
   alignment detection needs the actual set of a user's memories, not a
   relevance-ranked slice of them for one query) goes through
   AIMemoryService.list_memories() - already the platform's existing,
   unmodified bulk-listing method (MemoryAdapter already depends on this
   exact same AIMemoryService instance for its write path; this is the
   same collaborator, reused for a second, already-existing capability of
   its own, not a new one). AgentMemory.retrieve()/MemoryRetrievalPipeline
   have no such bulk/unfiltered mode - and are deliberately not asked for
   one, since "do not change retrieval behavior" is a hard constraint of
   this phase.

Nothing here talks to the database directly, adds a new repository
method, or adds a parameter to any existing platform method - it only
composes two already-existing, unmodified read paths.
"""

from datetime import datetime

from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
from app.services.ai.agents.specialists.personal_intelligence.shared.insight import Insight
from app.services.ai_memory_service import AIMemoryService
from app.services.context.types import ContextItem, ContextPackage

_DEFAULT_LIMIT = 10
_DEFAULT_MAX_CONTEXT_TOKENS = 4000
_DEFAULT_PAGE_SIZE = 100


class InsightMemoryService:
    def __init__(self, memory: AgentMemory | None = None, memory_service: AIMemoryService | None = None) -> None:
        self.memory = memory or MemoryAdapter()
        self.memory_service = memory_service or AIMemoryService()

    # --- write side: an Insight is just another Memory row -----------------------------------

    def remember_insight(self, insight: Insight, *, organization_id: int, user_id: int | None = None) -> None:
        self.memory.remember(
            insight.to_memory_content(),
            organization_id=organization_id,
            user_id=user_id,
            memory_type=insight.memory_type,
            title=insight.title,
        )

    # --- read side, relevance-ranked: recalling previously generated insights ----------------

    def recall_insights(
        self,
        query: str,
        *,
        organization_id: int,
        limit: int = _DEFAULT_LIMIT,
        max_context_tokens: int = _DEFAULT_MAX_CONTEXT_TOKENS,
    ) -> ContextPackage:
        return self.memory.retrieve(
            query, organization_id=organization_id, scope="memories", limit=limit, max_context_tokens=max_context_tokens
        )

    # --- read side, bulk: the raw corpus analysis needs ---------------------------------------

    def list_memory_facts(
        self,
        organization_id: int,
        *,
        since: datetime | None = None,
        memory_types: frozenset[str] | None = None,
        maximum: int = 200,
    ) -> tuple[ContextItem, ...]:
        """Every Memory row for this organization (paginated through the
        existing, unmodified AIMemoryService.list_memories()), optionally
        narrowed to a `since` cutoff and/or a set of `memory_types` -
        filtering happens here, client-side, over already-public Memory
        fields, never via a new query parameter on the platform's
        existing services.

        Returned as ContextItem (resource_type="memory", the same shape
        every other retrieved-memory item in this platform already takes)
        rather than a new type - metadata carries memory_type/title, which
        ContextItem's existing, optional metadata dict already has room
        for.
        """
        rows = []
        skip = 0
        page_size = min(maximum, _DEFAULT_PAGE_SIZE) or _DEFAULT_PAGE_SIZE
        while len(rows) < maximum:
            batch = self.memory_service.list_memories(organization_id, skip=skip, limit=page_size)
            if not batch:
                break
            rows.extend(batch)
            skip += page_size
            if len(batch) < page_size:
                break

        items = [
            ContextItem(
                resource_type="memory",
                resource_id=row.id,
                content=row.content,
                score=1.0,
                created_at=row.created_at,
                metadata={"memory_type": row.memory_type, "title": row.title or ""},
            )
            for row in rows
        ]
        if memory_types is not None:
            items = [item for item in items if item.metadata["memory_type"] in memory_types]
        if since is not None:
            items = [item for item in items if item.created_at is not None and item.created_at >= since]
        return tuple(items[:maximum])
