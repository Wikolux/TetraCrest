import pytest

from app.services.embedding.base_provider import EmbeddingProviderError
from app.services.embedding.openai_provider import OpenAIEmbeddingProvider
from app.services.embedding.provider_factory import EmbeddingProviderFactory
from settings import get_settings


def test_factory_returns_openai_provider_when_configured(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-small")
    get_settings.cache_clear()

    try:
        provider = EmbeddingProviderFactory.create()
        assert isinstance(provider, OpenAIEmbeddingProvider)
        assert provider.api_key == "test-key"
        assert provider.model == "text-embedding-3-small"
    finally:
        get_settings.cache_clear()


def test_factory_rejects_unsupported_provider(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "not-a-real-provider")
    get_settings.cache_clear()

    try:
        with pytest.raises(EmbeddingProviderError, match="Unsupported embedding provider"):
            EmbeddingProviderFactory.create()
    finally:
        get_settings.cache_clear()


def test_factory_accepts_explicit_settings_instead_of_global():
    settings = get_settings().model_copy(
        update={"embedding_provider": "openai", "openai_api_key": "explicit-key"}
    )

    provider = EmbeddingProviderFactory.create(settings)

    assert isinstance(provider, OpenAIEmbeddingProvider)
    assert provider.api_key == "explicit-key"


def test_factory_fails_fast_when_openai_selected_without_api_key(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()

    try:
        with pytest.raises(EmbeddingProviderError, match="requires OPENAI_API_KEY"):
            EmbeddingProviderFactory.create()
    finally:
        get_settings.cache_clear()


def test_factory_fails_fast_with_explicit_settings_missing_api_key():
    settings = get_settings().model_copy(
        update={"embedding_provider": "openai", "openai_api_key": None}
    )

    with pytest.raises(EmbeddingProviderError, match="requires OPENAI_API_KEY"):
        EmbeddingProviderFactory.create(settings)
