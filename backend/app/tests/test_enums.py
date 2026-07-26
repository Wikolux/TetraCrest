import json

from app.core.enums import EmbeddingProviderName, ResourceType, VectorStoreProviderName
from app.services.embedding.provider_factory import _PROVIDERS
from app.services.vector_store.store_factory import _STORES
from settings import get_settings


def test_resource_type_values_are_distinct_strings():
    values = {ResourceType.MEMORY, ResourceType.CONVERSATION_MESSAGE, ResourceType.KNOWLEDGE}
    assert len(values) == 3
    assert all(isinstance(value, str) for value in values)


def test_resource_type_members_equal_plain_strings():
    assert ResourceType.MEMORY == "memory"
    assert ResourceType.CONVERSATION_MESSAGE == "conversation_message"
    assert ResourceType.KNOWLEDGE == "knowledge"


def test_provider_factory_registry_keyed_by_enum():
    assert EmbeddingProviderName.OPENAI in _PROVIDERS
    # a plain string lookup must also hit the enum-keyed entry, since that's
    # exactly how settings.embedding_provider (a plain str) is used to look
    # up the registry at runtime
    assert "openai" in _PROVIDERS


def test_store_factory_registry_keyed_by_enums():
    assert VectorStoreProviderName.NULL in _STORES
    assert VectorStoreProviderName.PGVECTOR in _STORES
    assert "null" in _STORES
    assert "pgvector" in _STORES


def test_settings_defaults_match_enum_values():
    settings = get_settings()
    assert settings.embedding_provider == EmbeddingProviderName.OPENAI
    assert settings.vector_store_provider == VectorStoreProviderName.NULL


def test_enums_serialize_as_plain_strings():
    payload = json.dumps(
        {
            "resource_type": ResourceType.MEMORY,
            "embedding_provider": EmbeddingProviderName.OPENAI,
            "vector_store_provider": VectorStoreProviderName.PGVECTOR,
        }
    )
    assert json.loads(payload) == {
        "resource_type": "memory",
        "embedding_provider": "openai",
        "vector_store_provider": "pgvector",
    }


def test_enums_format_as_plain_strings_in_f_strings():
    assert f"{ResourceType.MEMORY}:42" == "memory:42"
