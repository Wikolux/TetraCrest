from typing import Callable

from app.services.context.context_builder import ContextBuilder
from app.services.context.types import ContextPackage
from app.services.ranking.ranking_engine import RankingEngine
from app.services.retrieval.adapters import (
    ranking_results_to_context_results,
    semantic_results_to_ranking_candidates,
)
from app.services.semantic_search_service import SemanticSearchService

# How much more than the caller's requested `limit` to retrieve before
# ranking/context-building narrow it back down. Ranking needs a wider pool
# than `limit` to meaningfully reorder (the top-`limit` by raw similarity
# isn't necessarily the top-`limit` by blended score), and ContextBuilder's
# own token budget - not this limit - is what actually determines the
# final result count. See MemoryRetrievalPipeline's docstring.
_OVER_FETCH_MULTIPLIER = 3
_MINIMUM_RETRIEVAL_LIMIT = 30


class MemoryRetrievalPipeline:
    """Orchestrates semantic retrieval, ranking, and context building into
    a single entry point.

    Owns exactly three collaborators - SemanticSearchService,
    RankingEngine, ContextBuilder - and does nothing those services
    already do: no embedding generation, no vector search, no ranking
    policy, no context-pipeline logic lives here. This class only decides
    *how much* to retrieve (the over-fetch limit) and *in what order* to
    call its three collaborators, converting between their types via the
    pure functions in adapters.py along the way.

    `limit` no longer directly bounds the final result count the way it
    does on SemanticSearchService: it's used to compute an over-fetched
    retrieval_limit, and the actual number of items that make it into the
    returned ContextPackage is governed by ContextBuilder's max_tokens
    budget instead. This is intentional - see the over-fetch constants
    above.

    Errors from any collaborator (EmbeddingProviderError, VectorStoreError
    from SemanticSearchService; anything RankingEngine/ContextBuilder
    raise) propagate unchanged. This is orchestration of a read path with
    no side effect to protect, so - exactly like SemanticSearchService
    itself - a failure must be visibly a failure, never silently
    swallowed into an empty result.
    """

    def __init__(
        self,
        semantic_search_service: SemanticSearchService | None = None,
        ranking_engine: RankingEngine | None = None,
        context_builder: ContextBuilder | None = None,
    ):
        self.semantic_search_service = semantic_search_service or SemanticSearchService()
        self.ranking_engine = ranking_engine or RankingEngine()
        self.context_builder = context_builder or ContextBuilder()

    def search_memories(
        self, query: str, organization_id: int, limit: int = 10, max_context_tokens: int = 4000
    ) -> ContextPackage:
        return self._search(
            self.semantic_search_service.search_memories, query, organization_id, limit, max_context_tokens
        )

    def search_conversation_messages(
        self, query: str, organization_id: int, limit: int = 10, max_context_tokens: int = 4000
    ) -> ContextPackage:
        return self._search(
            self.semantic_search_service.search_conversation_messages,
            query,
            organization_id,
            limit,
            max_context_tokens,
        )

    def search_all(
        self, query: str, organization_id: int, limit: int = 10, max_context_tokens: int = 4000
    ) -> ContextPackage:
        return self._search(
            self.semantic_search_service.search_all, query, organization_id, limit, max_context_tokens
        )

    def _search(
        self,
        retrieve: Callable[..., list],
        query: str,
        organization_id: int,
        limit: int,
        max_context_tokens: int,
    ) -> ContextPackage:
        retrieval_limit = self._retrieval_limit(limit)
        semantic_results = retrieve(query, organization_id, limit=retrieval_limit)

        ranking_candidates = semantic_results_to_ranking_candidates(semantic_results)
        ranked_candidates = self.ranking_engine.rank(ranking_candidates)
        context_inputs = ranking_results_to_context_results(ranked_candidates, semantic_results)

        return self.context_builder.build(context_inputs, max_tokens=max_context_tokens)

    @staticmethod
    def _retrieval_limit(limit: int) -> int:
        return max(limit * _OVER_FETCH_MULTIPLIER, _MINIMUM_RETRIEVAL_LIMIT)
