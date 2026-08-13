from datetime import datetime, timezone

import pytest

from app.services.context.types import ContextPackage
from app.services.embedding.base_provider import EmbeddingProviderError
from app.services.ranking.types import RankedCandidate, RankingCandidate
from app.services.retrieval.memory_retrieval_pipeline import MemoryRetrievalPipeline
from app.services.semantic_search_service import SemanticSearchResult
from app.services.vector_store.base_store import VectorStoreError

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


class _FakeSemanticSearchService:
    def __init__(self, results=None, error=None):
        self.results = results if results is not None else []
        self.error = error
        self.calls: list[dict] = []

    def _handle(self, method, query, organization_id, limit):
        self.calls.append({"method": method, "query": query, "organization_id": organization_id, "limit": limit})
        if self.error:
            raise self.error
        return self.results

    def search_memories(self, query, organization_id, limit=10):
        return self._handle("search_memories", query, organization_id, limit)

    def search_conversation_messages(self, query, organization_id, limit=10):
        return self._handle("search_conversation_messages", query, organization_id, limit)

    def search_all(self, query, organization_id, limit=10):
        return self._handle("search_all", query, organization_id, limit)


class _FakeRankingEngine:
    def __init__(self, ranked=None, error=None):
        self._ranked = ranked
        self.error = error
        self.received_candidates: list[RankingCandidate] | None = None

    def rank(self, candidates):
        self.received_candidates = candidates
        if self.error:
            raise self.error
        if self._ranked is not None:
            return self._ranked
        # default: preserve order, fixed score, so tests not overriding
        # ranked output can still assert something deterministic
        return [RankedCandidate(candidate=c, score=1.0) for c in candidates]


class _FakeContextBuilder:
    _SENTINEL_PACKAGE = ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)

    def __init__(self, package=None, error=None):
        self.package = package if package is not None else self._SENTINEL_PACKAGE
        self.error = error
        self.calls: list[dict] = []

    def build(self, ranked_results, max_tokens=4000):
        self.calls.append({"ranked_results": ranked_results, "max_tokens": max_tokens})
        if self.error:
            raise self.error
        return self.package


def _pipeline(semantic_search_service=None, ranking_engine=None, context_builder=None):
    return MemoryRetrievalPipeline(
        semantic_search_service=semantic_search_service or _FakeSemanticSearchService(),
        ranking_engine=ranking_engine or _FakeRankingEngine(),
        context_builder=context_builder or _FakeContextBuilder(),
    )


# --- search_memories / search_conversation_messages / search_all flows -----


def test_search_memories_calls_the_correct_underlying_method():
    semantic_search_service = _FakeSemanticSearchService(results=[_semantic_result(1)])
    pipeline = _pipeline(semantic_search_service=semantic_search_service)

    pipeline.search_memories("dark mode", organization_id=7)

    assert semantic_search_service.calls[0]["method"] == "search_memories"
    assert semantic_search_service.calls[0]["query"] == "dark mode"
    assert semantic_search_service.calls[0]["organization_id"] == 7


def test_search_conversation_messages_calls_the_correct_underlying_method():
    semantic_search_service = _FakeSemanticSearchService(results=[_semantic_result(1)])
    pipeline = _pipeline(semantic_search_service=semantic_search_service)

    pipeline.search_conversation_messages("ship date", organization_id=7)

    assert semantic_search_service.calls[0]["method"] == "search_conversation_messages"


def test_search_all_calls_the_correct_underlying_method():
    semantic_search_service = _FakeSemanticSearchService(results=[_semantic_result(1)])
    pipeline = _pipeline(semantic_search_service=semantic_search_service)

    pipeline.search_all("anything", organization_id=7)

    assert semantic_search_service.calls[0]["method"] == "search_all"


# --- over-fetch behavior ------------------------------------------------------


@pytest.mark.parametrize(
    ("limit", "expected_retrieval_limit"),
    [
        (10, 30),  # 10 * 3 = 30, ties with the minimum
        (5, 30),  # 5 * 3 = 15, below the minimum -> minimum wins
        (20, 60),  # 20 * 3 = 60, above the minimum -> multiplier wins
        (1, 30),
    ],
)
def test_over_fetch_limit_uses_multiplier_or_minimum_whichever_is_larger(limit, expected_retrieval_limit):
    semantic_search_service = _FakeSemanticSearchService(results=[])
    pipeline = _pipeline(semantic_search_service=semantic_search_service)

    pipeline.search_memories("query", organization_id=7, limit=limit)

    assert semantic_search_service.calls[0]["limit"] == expected_retrieval_limit


# --- collaborator delegation / adapter correctness ---------------------------


def test_ranking_engine_receives_candidates_converted_from_semantic_results():
    semantic_search_service = _FakeSemanticSearchService(
        results=[_semantic_result(1, similarity_score=0.42, metadata={"organization_id": 7})]
    )
    ranking_engine = _FakeRankingEngine()
    pipeline = _pipeline(semantic_search_service=semantic_search_service, ranking_engine=ranking_engine)

    pipeline.search_memories("query", organization_id=7)

    assert len(ranking_engine.received_candidates) == 1
    candidate = ranking_engine.received_candidates[0]
    assert isinstance(candidate, RankingCandidate)
    assert candidate.resource_id == 1
    assert candidate.similarity_score == 0.42
    assert candidate.metadata == {"organization_id": 7}


def test_ranking_candidates_do_not_carry_raw_content():
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(RankingCandidate)}
    assert "content" not in field_names


def test_context_builder_receives_max_context_tokens():
    context_builder = _FakeContextBuilder()
    semantic_search_service = _FakeSemanticSearchService(results=[_semantic_result(1)])
    pipeline = _pipeline(semantic_search_service=semantic_search_service, context_builder=context_builder)

    pipeline.search_memories("query", organization_id=7, max_context_tokens=1234)

    assert context_builder.calls[0]["max_tokens"] == 1234


def test_context_builder_receives_content_hydrated_ranked_results():
    semantic_search_service = _FakeSemanticSearchService(
        results=[_semantic_result(1, content="the actual content")]
    )
    context_builder = _FakeContextBuilder()
    pipeline = _pipeline(semantic_search_service=semantic_search_service, context_builder=context_builder)

    pipeline.search_memories("query", organization_id=7)

    received = context_builder.calls[0]["ranked_results"]
    assert len(received) == 1
    assert received[0].content == "the actual content"
    assert received[0].resource_id == 1


def test_context_builder_receives_the_ranking_engines_score_not_similarity_score():
    semantic_search_service = _FakeSemanticSearchService(results=[_semantic_result(1, similarity_score=0.9)])
    ranking_engine = _FakeRankingEngine(
        ranked=[
            RankedCandidate(
                candidate=RankingCandidate(
                    resource_type="memory", resource_id=1, similarity_score=0.9, created_at=_NOW
                ),
                score=0.15,
            )
        ]
    )
    context_builder = _FakeContextBuilder()
    pipeline = _pipeline(
        semantic_search_service=semantic_search_service, ranking_engine=ranking_engine, context_builder=context_builder
    )

    pipeline.search_memories("query", organization_id=7)

    assert context_builder.calls[0]["ranked_results"][0].score == 0.15


def test_context_builder_receives_results_in_ranking_engines_order():
    semantic_search_service = _FakeSemanticSearchService(
        results=[_semantic_result(1), _semantic_result(2), _semantic_result(3)]
    )

    def _reordering_rank(candidates):
        by_id = {c.resource_id: c for c in candidates}
        return [
            RankedCandidate(candidate=by_id[3], score=0.9),
            RankedCandidate(candidate=by_id[1], score=0.5),
            RankedCandidate(candidate=by_id[2], score=0.1),
        ]

    ranking_engine = _FakeRankingEngine()
    ranking_engine.rank = _reordering_rank
    context_builder = _FakeContextBuilder()
    pipeline = _pipeline(
        semantic_search_service=semantic_search_service, ranking_engine=ranking_engine, context_builder=context_builder
    )

    pipeline.search_memories("query", organization_id=7)

    received = context_builder.calls[0]["ranked_results"]
    assert [item.resource_id for item in received] == [3, 1, 2]


# --- ContextPackage passthrough ----------------------------------------------


def test_pipeline_returns_context_builders_output_unchanged():
    sentinel_package = ContextPackage(sections=[], estimated_tokens=42, item_count=1, truncated=True)
    context_builder = _FakeContextBuilder(package=sentinel_package)
    pipeline = _pipeline(context_builder=context_builder)

    result = pipeline.search_memories("query", organization_id=7)

    assert result is sentinel_package


# --- empty search results -----------------------------------------------------


def test_empty_semantic_results_flow_through_to_an_empty_ranking_call():
    semantic_search_service = _FakeSemanticSearchService(results=[])
    ranking_engine = _FakeRankingEngine()
    context_builder = _FakeContextBuilder()
    pipeline = _pipeline(
        semantic_search_service=semantic_search_service, ranking_engine=ranking_engine, context_builder=context_builder
    )

    pipeline.search_memories("query", organization_id=7)

    assert ranking_engine.received_candidates == []
    assert context_builder.calls[0]["ranked_results"] == []


def test_empty_semantic_results_still_returns_context_builders_package():
    sentinel_package = ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)
    context_builder = _FakeContextBuilder(package=sentinel_package)
    pipeline = _pipeline(semantic_search_service=_FakeSemanticSearchService(results=[]), context_builder=context_builder)

    result = pipeline.search_memories("query", organization_id=7)

    assert result is sentinel_package


# --- dependency injection -----------------------------------------------------


def test_injected_collaborators_are_used():
    semantic_search_service = _FakeSemanticSearchService(results=[])
    ranking_engine = _FakeRankingEngine()
    context_builder = _FakeContextBuilder()

    pipeline = MemoryRetrievalPipeline(
        semantic_search_service=semantic_search_service,
        ranking_engine=ranking_engine,
        context_builder=context_builder,
    )

    assert pipeline.semantic_search_service is semantic_search_service
    assert pipeline.ranking_engine is ranking_engine
    assert pipeline.context_builder is context_builder


def test_default_construction_builds_real_collaborators(monkeypatch):
    import app.services.retrieval.memory_retrieval_pipeline as module

    sentinel_search = _FakeSemanticSearchService()
    sentinel_ranking = _FakeRankingEngine()
    sentinel_context = _FakeContextBuilder()

    monkeypatch.setattr(module, "SemanticSearchService", lambda: sentinel_search)
    monkeypatch.setattr(module, "RankingEngine", lambda: sentinel_ranking)
    monkeypatch.setattr(module, "ContextBuilder", lambda: sentinel_context)

    pipeline = module.MemoryRetrievalPipeline()

    assert pipeline.semantic_search_service is sentinel_search
    assert pipeline.ranking_engine is sentinel_ranking
    assert pipeline.context_builder is sentinel_context


# --- error propagation ---------------------------------------------------------


def test_semantic_search_service_embedding_error_propagates():
    semantic_search_service = _FakeSemanticSearchService(error=EmbeddingProviderError("provider down"))
    pipeline = _pipeline(semantic_search_service=semantic_search_service)

    with pytest.raises(EmbeddingProviderError, match="provider down"):
        pipeline.search_memories("query", organization_id=7)


def test_semantic_search_service_vector_store_error_propagates():
    semantic_search_service = _FakeSemanticSearchService(error=VectorStoreError("store down"))
    pipeline = _pipeline(semantic_search_service=semantic_search_service)

    with pytest.raises(VectorStoreError, match="store down"):
        pipeline.search_all("query", organization_id=7)


def test_ranking_engine_error_propagates():
    semantic_search_service = _FakeSemanticSearchService(results=[_semantic_result(1)])
    ranking_engine = _FakeRankingEngine(error=RuntimeError("ranking exploded"))
    pipeline = _pipeline(semantic_search_service=semantic_search_service, ranking_engine=ranking_engine)

    with pytest.raises(RuntimeError, match="ranking exploded"):
        pipeline.search_memories("query", organization_id=7)


def test_context_builder_error_propagates():
    semantic_search_service = _FakeSemanticSearchService(results=[_semantic_result(1)])
    context_builder = _FakeContextBuilder(error=RuntimeError("context building exploded"))
    pipeline = _pipeline(semantic_search_service=semantic_search_service, context_builder=context_builder)

    with pytest.raises(RuntimeError, match="context building exploded"):
        pipeline.search_conversation_messages("query", organization_id=7)
