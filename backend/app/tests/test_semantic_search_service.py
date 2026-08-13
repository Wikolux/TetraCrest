from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from app.services.embedding.base_provider import EmbeddingProviderError
from app.services.semantic_search_service import SemanticSearchService
from app.services.vector_store.base_store import VectorStore, VectorStoreError
from app.services.vector_store.types import SearchResult

_DEFAULT_CREATED_AT = datetime(2024, 1, 1, tzinfo=timezone.utc)


@dataclass
class _Row:
    id: int
    organization_id: int
    content: str
    created_at: datetime = field(default=_DEFAULT_CREATED_AT)


class _FakeEmbeddingService:
    def __init__(self, vector=None, error=None):
        self.vector = vector or [0.1, 0.2, 0.3]
        self.error = error
        self.queries: list[str] = []

    def generate_embedding(self, text: str) -> list[float]:
        self.queries.append(text)
        if self.error:
            raise self.error
        return self.vector


class _FakeVectorStore(VectorStore):
    def __init__(self, results=None, error=None):
        self.results = results if results is not None else []
        self.error = error
        self.search_calls: list[dict] = []

    def save_vector(self, vector_id, vector, metadata=None):
        raise NotImplementedError

    def get_vector(self, vector_id):
        raise NotImplementedError

    def delete_vector(self, vector_id):
        raise NotImplementedError

    def health_check(self):
        return True

    def search(self, query_vector, organization_id, resource_type=None, limit=10):
        self.search_calls.append(
            {
                "query_vector": query_vector,
                "organization_id": organization_id,
                "resource_type": resource_type,
                "limit": limit,
            }
        )
        if self.error:
            raise self.error
        return self.results


class _FakeRepository:
    def __init__(self, rows: list[_Row]):
        self.rows = rows
        self.calls: list[tuple[list[int], int]] = []

    def get_many_for_organization(self, ids, organization_id):
        self.calls.append((list(ids), organization_id))
        return [row for row in self.rows if row.id in ids and row.organization_id == organization_id]


def _match(vector_id, resource_type, resource_id, organization_id, score, extra=None):
    metadata = {"organization_id": organization_id, "resource_type": resource_type, "resource_id": resource_id}
    if extra:
        metadata.update(extra)
    return SearchResult(vector_id=vector_id, score=score, metadata=metadata)


def _service(
    embedding_service=None,
    vector_store=None,
    memory_rows=None,
    message_rows=None,
):
    return SemanticSearchService(
        embedding_service=embedding_service or _FakeEmbeddingService(),
        vector_store=vector_store or _FakeVectorStore(),
        memory_repository=_FakeRepository(memory_rows or []),
        conversation_message_repository=_FakeRepository(message_rows or []),
    )


# --- embedding delegation --------------------------------------------------


def test_search_memories_generates_embedding_from_query_text():
    embedding_service = _FakeEmbeddingService()
    service = _service(embedding_service=embedding_service)

    service.search_memories("dark mode preference", organization_id=1)

    assert embedding_service.queries == ["dark mode preference"]


def test_search_conversation_messages_generates_embedding_from_query_text():
    embedding_service = _FakeEmbeddingService()
    service = _service(embedding_service=embedding_service)

    service.search_conversation_messages("what did we discuss", organization_id=1)

    assert embedding_service.queries == ["what did we discuss"]


def test_search_all_generates_embedding_from_query_text():
    embedding_service = _FakeEmbeddingService()
    service = _service(embedding_service=embedding_service)

    service.search_all("anything relevant", organization_id=1)

    assert embedding_service.queries == ["anything relevant"]


# --- vector search delegation ----------------------------------------------


def test_search_memories_calls_vector_store_with_memory_resource_type():
    vector_store = _FakeVectorStore()
    service = _service(embedding_service=_FakeEmbeddingService(vector=[0.9]), vector_store=vector_store)

    service.search_memories("query", organization_id=42, limit=5)

    call = vector_store.search_calls[0]
    assert call["query_vector"] == [0.9]
    assert call["organization_id"] == 42
    assert call["resource_type"] == "memory"
    assert call["limit"] == 5


def test_search_conversation_messages_calls_vector_store_with_conversation_message_resource_type():
    vector_store = _FakeVectorStore()
    service = _service(vector_store=vector_store)

    service.search_conversation_messages("query", organization_id=42, limit=3)

    call = vector_store.search_calls[0]
    assert call["resource_type"] == "conversation_message"
    assert call["limit"] == 3


def test_search_all_calls_vector_store_with_no_resource_type_filter():
    vector_store = _FakeVectorStore()
    service = _service(vector_store=vector_store)

    service.search_all("query", organization_id=42)

    call = vector_store.search_calls[0]
    assert call["resource_type"] is None
    assert call["limit"] == 10  # default


# --- repository hydration ---------------------------------------------------


def test_search_memories_hydrates_content_from_memory_repository():
    memory_row = _Row(id=1, organization_id=7, content="The user prefers dark mode.")
    vector_store = _FakeVectorStore(results=[_match("memory:1", "memory", 1, 7, score=0.05)])
    service = _service(vector_store=vector_store, memory_rows=[memory_row])

    results = service.search_memories("dark mode", organization_id=7)

    assert len(results) == 1
    assert results[0].resource_type == "memory"
    assert results[0].resource_id == 1
    assert results[0].content == "The user prefers dark mode."
    assert results[0].similarity_score == 0.05
    assert results[0].metadata["organization_id"] == 7


def test_search_memories_hydrates_created_at_from_the_underlying_resource():
    created_at = datetime(2023, 6, 15, tzinfo=timezone.utc)
    memory_row = _Row(id=1, organization_id=7, content="dated content", created_at=created_at)
    vector_store = _FakeVectorStore(results=[_match("memory:1", "memory", 1, 7, score=0.05)])
    service = _service(vector_store=vector_store, memory_rows=[memory_row])

    results = service.search_memories("query", organization_id=7)

    assert results[0].created_at == created_at


def test_search_conversation_messages_hydrates_content_from_message_repository():
    message_row = _Row(id=9, organization_id=7, content="Let's ship on Friday.")
    vector_store = _FakeVectorStore(
        results=[_match("conversation_message:9", "conversation_message", 9, 7, score=0.1)]
    )
    service = _service(vector_store=vector_store, message_rows=[message_row])

    results = service.search_conversation_messages("ship date", organization_id=7)

    assert len(results) == 1
    assert results[0].resource_type == "conversation_message"
    assert results[0].content == "Let's ship on Friday."


def test_hydration_uses_a_single_batched_repository_call():
    memory_rows = [_Row(id=1, organization_id=7, content="one"), _Row(id=2, organization_id=7, content="two")]
    vector_store = _FakeVectorStore(
        results=[
            _match("memory:1", "memory", 1, 7, score=0.1),
            _match("memory:2", "memory", 2, 7, score=0.2),
        ]
    )
    memory_repo = _FakeRepository(memory_rows)
    service = SemanticSearchService(
        embedding_service=_FakeEmbeddingService(),
        vector_store=vector_store,
        memory_repository=memory_repo,
        conversation_message_repository=_FakeRepository([]),
    )

    service.search_memories("query", organization_id=7)

    assert len(memory_repo.calls) == 1
    assert set(memory_repo.calls[0][0]) == {1, 2}


def test_hydration_skips_matches_for_deleted_or_missing_resources():
    # match references resource_id=99, which no longer exists in the repo
    vector_store = _FakeVectorStore(results=[_match("memory:99", "memory", 99, 7, score=0.1)])
    service = _service(vector_store=vector_store, memory_rows=[])

    results = service.search_memories("query", organization_id=7)

    assert results == []


# --- mixed resource search (search_all) -------------------------------------


def test_search_all_hydrates_and_interleaves_both_resource_types_in_order():
    memory_row = _Row(id=1, organization_id=7, content="memory content")
    message_row = _Row(id=2, organization_id=7, content="message content")
    vector_store = _FakeVectorStore(
        results=[
            _match("conversation_message:2", "conversation_message", 2, 7, score=0.05),
            _match("memory:1", "memory", 1, 7, score=0.2),
        ]
    )
    service = _service(vector_store=vector_store, memory_rows=[memory_row], message_rows=[message_row])

    results = service.search_all("query", organization_id=7)

    assert [r.resource_type for r in results] == ["conversation_message", "memory"]
    assert [r.content for r in results] == ["message content", "memory content"]


# --- tenant isolation ---------------------------------------------------------


def test_hydration_excludes_results_belonging_to_a_different_organization():
    # the repository fake enforces the tenant filter itself, exactly like
    # the real BaseRepository.get_many_for_organization does
    foreign_row = _Row(id=1, organization_id=999, content="not yours")
    vector_store = _FakeVectorStore(results=[_match("memory:1", "memory", 1, 999, score=0.1)])
    service = _service(vector_store=vector_store, memory_rows=[foreign_row])

    results = service.search_memories("query", organization_id=7)

    assert results == []


def test_search_passes_organization_id_through_to_vector_store_and_repositories():
    memory_row = _Row(id=1, organization_id=7, content="mine")
    vector_store = _FakeVectorStore(results=[_match("memory:1", "memory", 1, 7, score=0.1)])
    memory_repo = _FakeRepository([memory_row])
    service = SemanticSearchService(
        embedding_service=_FakeEmbeddingService(),
        vector_store=vector_store,
        memory_repository=memory_repo,
        conversation_message_repository=_FakeRepository([]),
    )

    service.search_memories("query", organization_id=7)

    assert vector_store.search_calls[0]["organization_id"] == 7
    assert memory_repo.calls[0][1] == 7


# --- empty search results -----------------------------------------------------


def test_search_memories_returns_empty_list_when_vector_store_finds_nothing():
    service = _service(vector_store=_FakeVectorStore(results=[]))

    assert service.search_memories("query", organization_id=7) == []


def test_search_all_returns_empty_list_when_vector_store_finds_nothing():
    service = _service(vector_store=_FakeVectorStore(results=[]))

    assert service.search_all("query", organization_id=7) == []


def test_empty_results_do_not_trigger_repository_calls():
    memory_repo = _FakeRepository([])
    message_repo = _FakeRepository([])
    service = SemanticSearchService(
        embedding_service=_FakeEmbeddingService(),
        vector_store=_FakeVectorStore(results=[]),
        memory_repository=memory_repo,
        conversation_message_repository=message_repo,
    )

    service.search_all("query", organization_id=7)

    assert memory_repo.calls == []
    assert message_repo.calls == []


# --- ranking order -------------------------------------------------------------


def test_results_preserve_the_vector_stores_similarity_order():
    memory_rows = [
        _Row(id=1, organization_id=7, content="least similar"),
        _Row(id=2, organization_id=7, content="most similar"),
        _Row(id=3, organization_id=7, content="middle"),
    ]
    # deliberately not pre-sorted by score, to prove the service doesn't re-sort
    vector_store = _FakeVectorStore(
        results=[
            _match("memory:2", "memory", 2, 7, score=0.01),
            _match("memory:3", "memory", 3, 7, score=0.5),
            _match("memory:1", "memory", 1, 7, score=0.9),
        ]
    )
    service = _service(vector_store=vector_store, memory_rows=memory_rows)

    results = service.search_memories("query", organization_id=7)

    assert [r.content for r in results] == ["most similar", "middle", "least similar"]
    assert [r.similarity_score for r in results] == [0.01, 0.5, 0.9]


# --- error propagation ----------------------------------------------------------


def test_embedding_provider_error_propagates_out_of_search():
    embedding_service = _FakeEmbeddingService(error=EmbeddingProviderError("provider down"))
    service = _service(embedding_service=embedding_service)

    with pytest.raises(EmbeddingProviderError, match="provider down"):
        service.search_memories("query", organization_id=7)


def test_vector_store_error_propagates_out_of_search():
    vector_store = _FakeVectorStore(error=VectorStoreError("store down"))
    service = _service(vector_store=vector_store)

    with pytest.raises(VectorStoreError, match="store down"):
        service.search_all("query", organization_id=7)


def test_vector_store_error_propagates_for_conversation_message_search():
    vector_store = _FakeVectorStore(error=VectorStoreError("store down"))
    service = _service(vector_store=vector_store)

    with pytest.raises(VectorStoreError, match="store down"):
        service.search_conversation_messages("query", organization_id=7)


# --- default construction ---------------------------------------------------


def test_default_construction_uses_embedding_service_and_vector_store_factory(monkeypatch):
    import app.services.semantic_search_service as module

    sentinel_embedding_service = _FakeEmbeddingService()
    sentinel_vector_store = _FakeVectorStore()

    monkeypatch.setattr(module, "EmbeddingService", lambda: sentinel_embedding_service)
    monkeypatch.setattr(module.VectorStoreFactory, "create", lambda: sentinel_vector_store)

    service = module.SemanticSearchService(db=object())

    assert service.embedding_service is sentinel_embedding_service
    assert service.vector_store is sentinel_vector_store
