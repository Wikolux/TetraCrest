import pytest

from app.services.vector_store.base_store import VectorStoreError
from app.services.vector_store.null_store import NullVectorStore
from app.services.vector_store.pgvector_store import PgVectorStore
from app.services.vector_store.store_factory import VectorStoreFactory
from settings import get_settings


def test_factory_returns_null_store_when_configured(monkeypatch):
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "null")
    get_settings.cache_clear()

    try:
        store = VectorStoreFactory.create()
        assert isinstance(store, NullVectorStore)
    finally:
        get_settings.cache_clear()


def test_factory_returns_pgvector_store_when_configured(monkeypatch):
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "pgvector")
    monkeypatch.setenv("VECTOR_STORE_TABLE", "custom_embeddings")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "8")
    get_settings.cache_clear()

    try:
        store = VectorStoreFactory.create()
        assert isinstance(store, PgVectorStore)
        assert store.table_name == "custom_embeddings"
        assert store.dimensions == 8
    finally:
        get_settings.cache_clear()


def test_factory_rejects_unsupported_provider(monkeypatch):
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "not-a-real-store")
    get_settings.cache_clear()

    try:
        with pytest.raises(VectorStoreError, match="Unsupported vector store provider"):
            VectorStoreFactory.create()
    finally:
        get_settings.cache_clear()


def test_factory_accepts_explicit_settings_instead_of_global():
    settings = get_settings().model_copy(update={"vector_store_provider": "null"})

    store = VectorStoreFactory.create(settings)

    assert isinstance(store, NullVectorStore)


def test_factory_fails_fast_when_pgvector_table_name_missing():
    settings = get_settings().model_copy(
        update={"vector_store_provider": "pgvector", "vector_store_table": ""}
    )

    with pytest.raises(VectorStoreError, match="requires vector_store_table"):
        VectorStoreFactory.create(settings)


def test_factory_fails_fast_when_pgvector_dimensions_invalid():
    settings = get_settings().model_copy(
        update={
            "vector_store_provider": "pgvector",
            "vector_store_table": "embedding_vectors",
            "embedding_dimensions": 0,
        }
    )

    with pytest.raises(VectorStoreError, match="positive embedding_dimensions"):
        VectorStoreFactory.create(settings)


def test_factory_does_not_validate_pgvector_settings_for_null_provider():
    settings = get_settings().model_copy(
        update={"vector_store_provider": "null", "embedding_dimensions": 0}
    )

    store = VectorStoreFactory.create(settings)

    assert isinstance(store, NullVectorStore)
