import dataclasses
from datetime import datetime, timezone

from app.services.retrieval.adapters import (
    ranking_results_to_context_results,
    semantic_results_to_ranking_candidates,
)
from app.services.ranking.types import RankedCandidate, RankingCandidate
from app.services.semantic_search_service import SemanticSearchResult

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _semantic_result(resource_id, resource_type="memory", content="content", similarity_score=0.1, metadata=None):
    return SemanticSearchResult(
        resource_type=resource_type,
        resource_id=resource_id,
        content=content,
        similarity_score=similarity_score,
        created_at=_NOW,
        metadata=metadata,
    )


# --- semantic_results_to_ranking_candidates ---------------------------------


def test_converts_fields_correctly():
    result = _semantic_result(1, content="hello", similarity_score=0.42, metadata={"organization_id": 7})

    candidates = semantic_results_to_ranking_candidates([result])

    assert len(candidates) == 1
    candidate = candidates[0]
    assert isinstance(candidate, RankingCandidate)
    assert candidate.resource_type == "memory"
    assert candidate.resource_id == 1
    assert candidate.similarity_score == 0.42
    assert candidate.created_at == _NOW
    assert candidate.metadata == {"organization_id": 7}


def test_drops_content_ranking_candidate_has_no_content_field():
    field_names = {f.name for f in dataclasses.fields(RankingCandidate)}

    assert "content" not in field_names


def test_preserves_input_order():
    results = [_semantic_result(3), _semantic_result(1), _semantic_result(2)]

    candidates = semantic_results_to_ranking_candidates(results)

    assert [c.resource_id for c in candidates] == [3, 1, 2]


def test_empty_input_returns_empty_list():
    assert semantic_results_to_ranking_candidates([]) == []


def test_is_a_pure_function_does_not_mutate_input():
    result = _semantic_result(1)
    original_content = result.content

    semantic_results_to_ranking_candidates([result])

    assert result.content == original_content


def test_semantic_results_to_ranking_candidates_is_deterministic():
    results = [_semantic_result(1), _semantic_result(2)]

    first_call = semantic_results_to_ranking_candidates(results)
    second_call = semantic_results_to_ranking_candidates(results)

    assert first_call == second_call


# --- ranking_results_to_context_results -------------------------------------


def _ranking_candidate(resource_id, resource_type="memory", similarity_score=0.1, metadata=None):
    return RankingCandidate(
        resource_type=resource_type,
        resource_id=resource_id,
        similarity_score=similarity_score,
        created_at=_NOW,
        metadata=metadata,
    )


def test_reattaches_content_from_matching_semantic_result():
    semantic_results = [_semantic_result(1, content="the original content")]
    ranked = [RankedCandidate(candidate=_ranking_candidate(1), score=0.9)]

    context_results = ranking_results_to_context_results(ranked, semantic_results)

    assert len(context_results) == 1
    assert context_results[0].content == "the original content"


def test_uses_ranking_engines_final_score_not_similarity_score():
    semantic_results = [_semantic_result(1, similarity_score=0.05)]
    ranked = [RankedCandidate(candidate=_ranking_candidate(1, similarity_score=0.05), score=0.77)]

    context_results = ranking_results_to_context_results(ranked, semantic_results)

    assert context_results[0].score == 0.77


def test_preserves_metadata_and_created_at_from_the_candidate():
    metadata = {"organization_id": 7}
    semantic_results = [_semantic_result(1)]
    ranked = [RankedCandidate(candidate=_ranking_candidate(1, metadata=metadata), score=0.5)]

    context_results = ranking_results_to_context_results(ranked, semantic_results)

    assert context_results[0].metadata == metadata
    assert context_results[0].created_at == _NOW


def test_follows_ranked_candidates_order_not_semantic_results_order():
    semantic_results = [_semantic_result(1), _semantic_result(2), _semantic_result(3)]
    ranked = [
        RankedCandidate(candidate=_ranking_candidate(3), score=0.9),
        RankedCandidate(candidate=_ranking_candidate(1), score=0.5),
        RankedCandidate(candidate=_ranking_candidate(2), score=0.1),
    ]

    context_results = ranking_results_to_context_results(ranked, semantic_results)

    assert [r.resource_id for r in context_results] == [3, 1, 2]


def test_matches_by_resource_type_and_resource_id_together():
    # same resource_id, different resource_type - must not cross-match
    memory_result = _semantic_result(1, resource_type="memory", content="memory content")
    message_result = _semantic_result(1, resource_type="conversation_message", content="message content")
    ranked = [RankedCandidate(candidate=_ranking_candidate(1, resource_type="conversation_message"), score=0.5)]

    context_results = ranking_results_to_context_results(ranked, [memory_result, message_result])

    assert context_results[0].content == "message content"


def test_unmatched_ranked_candidate_gets_empty_content_instead_of_raising():
    ranked = [RankedCandidate(candidate=_ranking_candidate(999), score=0.5)]

    context_results = ranking_results_to_context_results(ranked, [])

    assert context_results[0].content == ""


def test_empty_ranked_candidates_returns_empty_list():
    assert ranking_results_to_context_results([], [_semantic_result(1)]) == []


def test_ranking_results_to_context_results_is_deterministic():
    semantic_results = [_semantic_result(1)]
    ranked = [RankedCandidate(candidate=_ranking_candidate(1), score=0.5)]

    first_call = ranking_results_to_context_results(ranked, semantic_results)
    second_call = ranking_results_to_context_results(ranked, semantic_results)

    assert first_call == second_call
