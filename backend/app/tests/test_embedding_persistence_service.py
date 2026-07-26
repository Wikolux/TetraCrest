import pytest

from app.services.embedding.base_provider import EmbeddingProvider
from app.services.embedding_persistence_service import EmbeddingPersistenceService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store.base_store import VectorStore
from app.services.vector_store.types import VectorMetadata


class _FakeProvider(EmbeddingProvider):
    def __init__(self, vectors, healthy: bool = True, model_name: str = "fake-model"):
        self.vectors = vectors
        self.healthy = healthy
        self._model_name = model_name
        self.received_texts: list[str] | None = None
        self.embed_calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.received_texts = texts
        self.embed_calls += 1
        return self.vectors

    def health_check(self) -> bool:
        return self.healthy

    @property
    def model_name(self) -> str:
        return self._model_name


class _FakeVectorStore(VectorStore):
    def __init__(self, healthy: bool = True):
        self.saved: list[tuple] = []
        self.deleted: list[str] = []
        self.get_calls: list[str] = []
        self.healthy = healthy
        self.health_checks = 0
        self.stored: dict[str, list[float]] = {}

    def save_vector(self, vector_id, vector, metadata=None):
        self.saved.append((vector_id, vector, metadata))
        self.stored[vector_id] = vector

    def get_vector(self, vector_id):
        self.get_calls.append(vector_id)
        return self.stored.get(vector_id)

    def delete_vector(self, vector_id):
        self.deleted.append(vector_id)
        return vector_id in self.stored

    def health_check(self):
        self.health_checks += 1
        return self.healthy

    def search(self, query_vector, organization_id, resource_type=None, limit=10):
        return []


def _service(vectors=None):
    provider = _FakeProvider(vectors=vectors or [[0.1, 0.2, 0.3]])
    embedding_service = EmbeddingService(provider=provider)
    vector_store = _FakeVectorStore()
    return EmbeddingPersistenceService(embedding_service=embedding_service, vector_store=vector_store)


def test_generate_and_store_generates_embedding_exactly_once():
    provider = _FakeProvider(vectors=[[0.1, 0.2, 0.3]])
    embedding_service = EmbeddingService(provider=provider)
    vector_store = _FakeVectorStore()
    service = EmbeddingPersistenceService(embedding_service=embedding_service, vector_store=vector_store)

    service.generate_and_store("memory:1", "hello world")

    assert provider.received_texts == ["hello world"]


def test_generate_and_store_saves_vector_exactly_once():
    provider = _FakeProvider(vectors=[[0.1, 0.2, 0.3]])
    embedding_service = EmbeddingService(provider=provider)
    vector_store = _FakeVectorStore()
    service = EmbeddingPersistenceService(embedding_service=embedding_service, vector_store=vector_store)

    service.generate_and_store("memory:1", "hello world")

    assert len(vector_store.saved) == 1


def test_generate_and_store_passes_dict_metadata_through_with_embedding_model_added():
    service = _service()
    vector_store = service.vector_store
    metadata = {"organization_id": 7, "source": "memory"}

    service.generate_and_store("memory:1", "hello world", metadata=metadata)

    vector_id, vector, saved_metadata = vector_store.saved[0]
    assert vector_id == "memory:1"
    assert saved_metadata == {"organization_id": 7, "source": "memory", "embedding_model": "fake-model"}
    # the caller's own dict is never mutated - a copy is stored instead
    assert metadata == {"organization_id": 7, "source": "memory"}
    assert saved_metadata is not metadata


def test_generate_and_store_converts_vector_metadata_to_dict():
    service = _service()
    vector_store = service.vector_store
    metadata = VectorMetadata(organization_id=7, resource_type="memory", resource_id=1)

    service.generate_and_store("memory:1", "hello world", metadata=metadata)

    _, _, saved_metadata = vector_store.saved[0]
    assert saved_metadata == {
        "organization_id": 7,
        "resource_type": "memory",
        "resource_id": 1,
        "embedding_model": "fake-model",
    }


def test_generate_and_store_overwrites_caller_supplied_embedding_model():
    # embedding_model always reflects the provider actually used, never a
    # caller-supplied (possibly stale) value.
    service = _service()
    vector_store = service.vector_store
    metadata = VectorMetadata(
        organization_id=7, resource_type="memory", resource_id=1, embedding_model="some-other-model"
    )

    service.generate_and_store("memory:1", "hello world", metadata=metadata)

    _, _, saved_metadata = vector_store.saved[0]
    assert saved_metadata["embedding_model"] == "fake-model"


def test_generate_and_store_returns_generated_vector():
    service = _service(vectors=[[0.5, 0.6]])

    result = service.generate_and_store("memory:1", "hello world")

    assert result == [0.5, 0.6]


def test_generate_and_store_saves_the_generated_vector():
    service = _service(vectors=[[0.5, 0.6]])

    service.generate_and_store("memory:1", "hello world")

    _, saved_vector, _ = service.vector_store.saved[0]
    assert saved_vector == [0.5, 0.6]


def test_get_vector_delegates_to_vector_store():
    service = _service()
    service.vector_store.stored["memory:1"] = [0.1, 0.2]

    result = service.get_vector("memory:1")

    assert result == [0.1, 0.2]
    assert service.vector_store.get_calls == ["memory:1"]


def test_delete_vector_delegates_to_vector_store():
    service = _service()
    service.vector_store.stored["memory:1"] = [0.1, 0.2]

    result = service.delete_vector("memory:1")

    assert result is True
    assert service.vector_store.deleted == ["memory:1"]


def test_health_check_returns_true_for_both_when_healthy():
    service = _service()

    result = service.health_check()

    assert result == {"embedding_provider": True, "vector_store": True}
    assert service.vector_store.health_checks == 1


def test_health_check_reports_unhealthy_provider_independently():
    provider = _FakeProvider(vectors=[[0.1]], healthy=False)
    embedding_service = EmbeddingService(provider=provider)
    vector_store = _FakeVectorStore(healthy=True)
    service = EmbeddingPersistenceService(embedding_service=embedding_service, vector_store=vector_store)

    result = service.health_check()

    assert result == {"embedding_provider": False, "vector_store": True}


def test_health_check_reports_unhealthy_vector_store_independently():
    provider = _FakeProvider(vectors=[[0.1]], healthy=True)
    embedding_service = EmbeddingService(provider=provider)
    vector_store = _FakeVectorStore(healthy=False)
    service = EmbeddingPersistenceService(embedding_service=embedding_service, vector_store=vector_store)

    result = service.health_check()

    assert result == {"embedding_provider": True, "vector_store": False}


def test_default_construction_uses_embedding_service_and_vector_store_factory(monkeypatch):
    import app.services.embedding_persistence_service as module

    sentinel_provider = _FakeProvider(vectors=[[0.1]])
    sentinel_embedding_service = EmbeddingService(provider=sentinel_provider)
    sentinel_store = _FakeVectorStore()

    monkeypatch.setattr(module, "EmbeddingService", lambda: sentinel_embedding_service)
    monkeypatch.setattr(module.VectorStoreFactory, "create", lambda: sentinel_store)

    service = module.EmbeddingPersistenceService()

    assert service.embedding_service is sentinel_embedding_service
    assert service.vector_store is sentinel_store


def test_generate_and_store_many_uses_a_single_batched_provider_call():
    provider = _FakeProvider(vectors=[[0.1], [0.2], [0.3]])
    embedding_service = EmbeddingService(provider=provider)
    vector_store = _FakeVectorStore()
    service = EmbeddingPersistenceService(embedding_service=embedding_service, vector_store=vector_store)

    service.generate_and_store_many(["a:1", "a:2", "a:3"], ["one", "two", "three"])

    assert provider.embed_calls == 1
    assert provider.received_texts == ["one", "two", "three"]


def test_generate_and_store_many_saves_every_vector_in_order():
    service = _service()
    provider = service.embedding_service.provider
    provider.vectors = [[0.1], [0.2], [0.3]]

    service.generate_and_store_many(["a:1", "a:2", "a:3"], ["one", "two", "three"])

    assert [call[0] for call in service.vector_store.saved] == ["a:1", "a:2", "a:3"]
    assert [call[1] for call in service.vector_store.saved] == [[0.1], [0.2], [0.3]]


def test_generate_and_store_many_returns_generated_vectors_preserving_order():
    service = _service()
    provider = service.embedding_service.provider
    provider.vectors = [[0.1], [0.2], [0.3]]

    result = service.generate_and_store_many(["a:1", "a:2", "a:3"], ["one", "two", "three"])

    assert result == [[0.1], [0.2], [0.3]]


def test_generate_and_store_many_passes_per_item_metadata_through():
    service = _service()
    provider = service.embedding_service.provider
    provider.vectors = [[0.1], [0.2]]
    metadata = [
        {"organization_id": 1},
        VectorMetadata(organization_id=2, resource_type="memory", resource_id=9),
    ]

    service.generate_and_store_many(["a:1", "a:2"], ["one", "two"], metadata=metadata)

    saved_metadata = [call[2] for call in service.vector_store.saved]
    assert saved_metadata == [
        {"organization_id": 1, "embedding_model": "fake-model"},
        {"organization_id": 2, "resource_type": "memory", "resource_id": 9, "embedding_model": "fake-model"},
    ]


def test_generate_and_store_many_stamps_embedding_model_when_no_metadata_given():
    service = _service()
    provider = service.embedding_service.provider
    provider.vectors = [[0.1], [0.2]]

    service.generate_and_store_many(["a:1", "a:2"], ["one", "two"])

    assert [call[2] for call in service.vector_store.saved] == [
        {"embedding_model": "fake-model"},
        {"embedding_model": "fake-model"},
    ]


def test_generate_and_store_many_rejects_mismatched_vector_ids_and_texts():
    service = _service()

    with pytest.raises(ValueError, match="same length"):
        service.generate_and_store_many(["a:1"], ["one", "two"])


def test_generate_and_store_many_rejects_mismatched_metadata_length():
    service = _service()

    with pytest.raises(ValueError, match="same length"):
        service.generate_and_store_many(["a:1", "a:2"], ["one", "two"], metadata=[{"x": 1}])
