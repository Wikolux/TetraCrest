from app.core.constants import (
    EMBEDDING_PROVIDER_OPENAI,
    RESOURCE_CONVERSATION_MESSAGE,
    RESOURCE_KNOWLEDGE,
    RESOURCE_MEMORY,
    VECTOR_STORE_NULL,
    VECTOR_STORE_PGVECTOR,
)
from app.services.embedding.provider_factory import _PROVIDERS
from app.services.vector_store.store_factory import _STORES
from settings import get_settings


def test_resource_constants_are_distinct_strings():
    values = {RESOURCE_MEMORY, RESOURCE_CONVERSATION_MESSAGE, RESOURCE_KNOWLEDGE}
    assert len(values) == 3
    assert all(isinstance(value, str) for value in values)


def test_provider_factory_registry_keyed_by_constant():
    assert EMBEDDING_PROVIDER_OPENAI in _PROVIDERS


def test_store_factory_registry_keyed_by_constants():
    assert VECTOR_STORE_NULL in _STORES
    assert VECTOR_STORE_PGVECTOR in _STORES


def test_settings_defaults_match_constants():
    settings = get_settings()
    assert settings.embedding_provider == EMBEDDING_PROVIDER_OPENAI
    assert settings.vector_store_provider == VECTOR_STORE_NULL
