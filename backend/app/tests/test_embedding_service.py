import httpx
import pytest

from app.services.embedding.base_provider import EmbeddingProvider, EmbeddingProviderError
from app.services.embedding.openai_provider import OpenAIEmbeddingProvider
import app.services.embedding_service as embedding_service_module
from app.services.embedding_service import EmbeddingService


class _FakeProvider(EmbeddingProvider):
    def __init__(self, vectors=None, error=None):
        self.vectors = vectors
        self.error = error
        self.received_texts: list[str] | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.received_texts = texts
        if self.error:
            raise self.error
        return self.vectors


def test_generate_embedding_delegates_to_provider_and_unwraps_single_result():
    provider = _FakeProvider(vectors=[[0.1, 0.2, 0.3]])
    service = EmbeddingService(provider=provider)

    result = service.generate_embedding("hello world")

    assert result == [0.1, 0.2, 0.3]
    assert provider.received_texts == ["hello world"]


def test_generate_embeddings_delegates_to_provider_and_preserves_order():
    provider = _FakeProvider(vectors=[[0.1], [0.2], [0.3]])
    service = EmbeddingService(provider=provider)

    result = service.generate_embeddings(["a", "b", "c"])

    assert result == [[0.1], [0.2], [0.3]]
    assert provider.received_texts == ["a", "b", "c"]


def test_generate_embeddings_propagates_provider_errors():
    provider = _FakeProvider(error=EmbeddingProviderError("provider is down"))
    service = EmbeddingService(provider=provider)

    with pytest.raises(EmbeddingProviderError, match="provider is down"):
        service.generate_embeddings(["hello"])


def test_embedding_service_delegates_provider_creation_to_factory(monkeypatch):
    sentinel_provider = _FakeProvider(vectors=[[0.9]])
    calls: list[None] = []

    def _fake_create():
        calls.append(None)
        return sentinel_provider

    monkeypatch.setattr(embedding_service_module.EmbeddingProviderFactory, "create", _fake_create)

    service = EmbeddingService()

    assert service.provider is sentinel_provider
    assert len(calls) == 1


def test_embedding_service_has_no_vector_store_attribute():
    service = EmbeddingService(provider=_FakeProvider(vectors=[[0.1]]))

    assert not hasattr(service, "vector_store")


def _fake_post(json_body: dict, status_code: int = 200):
    def _post(url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(status_code, json=json_body, request=request)

    return _post


def _fake_post_connection_error():
    def _post(url, **kwargs):
        raise httpx.ConnectError("Connection failed", request=httpx.Request("POST", url))

    return _post


def test_openai_provider_returns_embeddings_in_input_order(monkeypatch):
    # OpenAI's API can return items out of order; the provider must
    # resort by "index" rather than trust response ordering.
    monkeypatch.setattr(
        httpx,
        "post",
        _fake_post(
            {
                "data": [
                    {"index": 1, "embedding": [0.2, 0.2]},
                    {"index": 0, "embedding": [0.1, 0.1]},
                ]
            }
        ),
    )
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")

    result = provider.embed(["first", "second"])

    assert result == [[0.1, 0.1], [0.2, 0.2]]


def test_openai_provider_returns_empty_list_for_no_texts():
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")

    assert provider.embed([]) == []


def test_openai_provider_requires_api_key():
    provider = OpenAIEmbeddingProvider(api_key=None, model="text-embedding-3-small")

    with pytest.raises(EmbeddingProviderError, match="API key is not configured"):
        provider.embed(["hello"])


def test_openai_provider_wraps_connection_errors(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post_connection_error())
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")

    with pytest.raises(EmbeddingProviderError, match="OpenAI embedding request failed"):
        provider.embed(["hello"])


def test_openai_provider_wraps_http_error_status(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post({"error": {"message": "bad request"}}, status_code=400))
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")

    with pytest.raises(EmbeddingProviderError, match="OpenAI embedding request failed"):
        provider.embed(["hello"])


def test_openai_provider_wraps_malformed_response(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post({"unexpected": "shape"}))
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")

    with pytest.raises(EmbeddingProviderError, match="malformed"):
        provider.embed(["hello"])


def test_openai_provider_health_check_true_when_api_key_configured():
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")

    assert provider.health_check() is True


def test_openai_provider_health_check_false_when_api_key_missing():
    provider = OpenAIEmbeddingProvider(api_key=None, model="text-embedding-3-small")

    assert provider.health_check() is False


def test_base_provider_health_check_defaults_to_true():
    assert _FakeProvider(vectors=[[0.1]]).health_check() is True
