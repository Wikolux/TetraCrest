"""MemoryAdapter - a thin wrapper over the existing MemoryRetrievalPipeline
and (M20.6) AIMemoryService, and the platform's concrete AgentMemory
implementation.

Never reimplements retrieval, ranking, embedding, or storage - every
method here is either a direct passthrough to MemoryRetrievalPipeline/
AIMemoryService, or a thin router onto one of those passthroughs. Exists
so a specialist depends on this small, easily-fakeable seam in tests
rather than importing MemoryRetrievalPipeline/AIMemoryService (and,
transitively, SemanticSearchService's and AIMemoryService's own database/
embedding/vector-store dependencies) directly.

retrieve_memories()/retrieve_conversations()/retrieve_all() are the
original, MemoryRetrievalPipeline-shaped methods (query + organization_id
+ limit/max_context_tokens) and are unchanged - existing callers keep
working exactly as before. remember()/retrieve()/forget()/search() satisfy
AgentMemory (app.services.ai.agents.memory): retrieve()/search() route to
whichever of the three passthroughs above matches the requested scope
(default "all", matching retrieve_all()'s existing behavior) - no new
retrieval logic, purely dispatch.

remember()/forget() (CP-01.2) close the gap flagged since M20.6 and
CP-01's own Architecture.md §20: they delegate to AIMemoryService
(app.services.ai_memory_service), the platform's existing write-path
service for the Memory Framework - no parallel storage mechanism is
introduced. This is additive completion of an already-declared,
previously-unimplemented AgentMemory method, not a redesign of the
Memory Framework or of AgentMemory's contract.
"""

from typing import Any

from app.services.ai.agents.memory import AgentMemory
from app.services.ai_memory_service import AIMemoryService
from app.services.context.types import ContextPackage
from app.services.retrieval.memory_retrieval_pipeline import MemoryRetrievalPipeline

_RETRIEVAL_SCOPES = ("all", "memories", "conversations")


class MemoryAdapter(AgentMemory):
    def __init__(
        self,
        pipeline: MemoryRetrievalPipeline | None = None,
        memory_service: AIMemoryService | None = None,
    ) -> None:
        self.pipeline = pipeline or MemoryRetrievalPipeline()
        self.memory_service = memory_service or AIMemoryService()

    def retrieve_memories(
        self, query: str, organization_id: int, limit: int = 10, max_context_tokens: int = 4000
    ) -> ContextPackage:
        return self.pipeline.search_memories(query, organization_id, limit=limit, max_context_tokens=max_context_tokens)

    def retrieve_conversations(
        self, query: str, organization_id: int, limit: int = 10, max_context_tokens: int = 4000
    ) -> ContextPackage:
        return self.pipeline.search_conversation_messages(
            query, organization_id, limit=limit, max_context_tokens=max_context_tokens
        )

    def retrieve_all(
        self, query: str, organization_id: int, limit: int = 10, max_context_tokens: int = 4000
    ) -> ContextPackage:
        return self.pipeline.search_all(query, organization_id, limit=limit, max_context_tokens=max_context_tokens)

    # --- AgentMemory contract -----------------------------------------------------------------

    def retrieve(self, query: str, **kwargs: Any) -> ContextPackage:
        """AgentMemory.retrieve(): recall whatever is most relevant to
        query. Routes to retrieve_memories()/retrieve_conversations()/
        retrieve_all() by an optional scope=... kwarg ("memories",
        "conversations", or the default "all") - every other kwarg
        (organization_id, limit, max_context_tokens) passes straight
        through to the matching method, unchanged."""
        organization_id = kwargs.pop("organization_id")
        scope = kwargs.pop("scope", "all")
        if scope == "memories":
            return self.retrieve_memories(query, organization_id, **kwargs)
        if scope == "conversations":
            return self.retrieve_conversations(query, organization_id, **kwargs)
        if scope != "all":
            raise ValueError(f"Unknown retrieval scope: {scope!r} (expected one of {_RETRIEVAL_SCOPES})")
        return self.retrieve_all(query, organization_id, **kwargs)

    def search(self, query: str, **kwargs: Any) -> ContextPackage:
        """AgentMemory.search(): search across everything remembered.
        There is exactly one retrieval mechanism in this platform
        (MemoryRetrievalPipeline) - search() and retrieve() are the same
        operation here, not two different implementations, so search()
        simply delegates to retrieve() rather than duplicating its
        scope-routing logic."""
        return self.retrieve(query, **kwargs)

    def remember(self, item: Any, **kwargs: Any) -> None:
        """AgentMemory.remember(): persist `item` (coerced to text if not
        already a string) as a new Memory row, via AIMemoryService -
        never a parallel store. Required: organization_id. Optional:
        user_id, memory_type (default "general"), title.

        Returns None, exactly matching AgentMemory's frozen signature -
        this method never hands back the created row's id. A caller that
        needs to later forget() what it just remembered finds it again
        via retrieve()/search() (whose ContextItem.resource_id is that
        same id) rather than being handed one directly here - consistent
        with this platform being a semantic-retrieval memory system, not
        an addressable CRUD store.
        """
        organization_id = kwargs.pop("organization_id")
        content = item if isinstance(item, str) else str(item)
        self.memory_service.create_memory(
            organization_id,
            content,
            user_id=kwargs.pop("user_id", None),
            memory_type=kwargs.pop("memory_type", "general"),
            title=kwargs.pop("title", None),
        )

    def forget(self, item_id: str) -> None:
        """AgentMemory.forget(): delete a previously remembered item.

        AgentMemory.forget()'s frozen signature is `(self, item_id: str)`
        only - no organization_id, no **kwargs - but AIMemoryService's
        delete is tenant-scoped and requires one. item_id is therefore
        the composite string "{organization_id}:{memory_id}" - exactly
        what a caller can reconstruct from a retrieve()/search() result's
        ContextItem.resource_id plus the organization_id it already has
        from its own execution context.
        """
        organization_id, memory_id = self._parse_item_id(item_id)
        self.memory_service.delete_memory(memory_id, organization_id)

    @staticmethod
    def _parse_item_id(item_id: str) -> tuple[int, int]:
        try:
            organization_id_str, memory_id_str = item_id.split(":", 1)
            return int(organization_id_str), int(memory_id_str)
        except (ValueError, AttributeError) as exc:
            raise ValueError(
                f"forget() expects item_id in 'organization_id:memory_id' form, got {item_id!r}"
            ) from exc
