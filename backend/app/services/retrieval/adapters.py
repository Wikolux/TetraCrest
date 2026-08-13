"""Pure conversion functions across the SemanticSearchResult -> RankingCandidate
-> ContextBuilder type boundary.

Every function here is stateless and side-effect free: given the same
input, always the same output, no mutation of arguments, no I/O. This is
the only place that bridges the three subsystems' otherwise-independent
types - none of SemanticSearchService, RankingEngine, or ContextBuilder
import from one another, and this module doesn't change that; it only
translates between their existing shapes.
"""

from app.services.ranking.types import RankedCandidate, RankingCandidate
from app.services.retrieval.types import RetrievalResult
from app.services.semantic_search_service import SemanticSearchResult


def semantic_results_to_ranking_candidates(
    semantic_results: list[SemanticSearchResult],
) -> list[RankingCandidate]:
    """Convert SemanticSearchResults into the RankingCandidates RankingEngine
    needs to score them.

    Drops `content` - RankingStrategy.score() never needs it - and carries
    everything else through unchanged, in the same order.
    """
    return [
        RankingCandidate(
            resource_type=result.resource_type,
            resource_id=result.resource_id,
            similarity_score=result.similarity_score,
            created_at=result.created_at,
            metadata=result.metadata,
        )
        for result in semantic_results
    ]


def ranking_results_to_context_results(
    ranked_candidates: list[RankedCandidate],
    semantic_results: list[SemanticSearchResult],
) -> list[RetrievalResult]:
    """Convert RankingEngine's output into ContextBuilder's input.

    Re-attaches `content` (dropped by semantic_results_to_ranking_candidates)
    by matching each ranked candidate back to its originating
    SemanticSearchResult via (resource_type, resource_id), and uses
    RankingEngine's final blended score in place of the raw similarity
    score. Order follows ranked_candidates (RankingEngine's best-first
    ordering), not semantic_results' original order.

    A ranked candidate with no matching semantic result (shouldn't happen
    given these two lists are 1:1 by construction in
    MemoryRetrievalPipeline) gets empty content rather than raising -
    this function never fails on its own account.
    """
    content_by_key = {
        (result.resource_type, result.resource_id): result.content for result in semantic_results
    }

    context_results = []
    for ranked in ranked_candidates:
        candidate = ranked.candidate
        key = (candidate.resource_type, candidate.resource_id)
        context_results.append(
            RetrievalResult(
                resource_type=candidate.resource_type,
                resource_id=candidate.resource_id,
                content=content_by_key.get(key, ""),
                score=ranked.score,
                created_at=candidate.created_at,
                metadata=candidate.metadata,
            )
        )
    return context_results
