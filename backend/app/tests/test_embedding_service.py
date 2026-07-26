import httpx
import pytest

from app.services.embedding.base_provider import EmbeddingProvider, EmbeddingProviderError
import app.services.embedding.openai_provider as openai_provider_module
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


class _CallCountingPost:
    """Fails a fixed number of times, then succeeds - or always fails."""

    def __init__(self, failures_then_success: int | None = None, failure_status: int = 500):
        self.calls = 0
        self.failures_then_success = failures_then_success
        self.failure_status = failure_status

    def __call__(self, url, **kwargs):
        self.calls += 1
        should_fail = (
            self.failures_then_success is None or self.calls <= self.failures_then_success
        )
        if should_fail:
            request = httpx.Request("POST", url)
            response = httpx.Response(self.failure_status, json={"error": {"message": "failing"}}, request=request)
            raise httpx.HTTPStatusError("failing", request=request, response=response)
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.1]}]}, request=request)


@pytest.fixture()
def no_sleep(monkeypatch):
    """Skip real delays for retry tests, recording what would have slept."""
    delays: list[float] = []
    monkeypatch.setattr(openai_provider_module.time, "sleep", lambda seconds: delays.append(seconds))
    return delays


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


def test_openai_provider_wraps_connection_errors(monkeypatch, no_sleep):
    monkeypatch.setattr(httpx, "post", _fake_post_connection_error())
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small", max_retries=1)

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


def test_openai_provider_model_name_returns_configured_model():
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")

    assert provider.model_name == "text-embedding-3-small"


def test_base_provider_model_name_defaults_to_unknown():
    assert _FakeProvider(vectors=[[0.1]]).model_name == "unknown"


# --- retry logic -------------------------------------------------------


def test_openai_provider_retries_transient_failure_then_succeeds(monkeypatch, no_sleep):
    fake_post = _CallCountingPost(failures_then_success=2)
    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small", max_retries=3)

    result = provider.embed(["hello"])

    assert result == [[0.1, 0.1]]
    assert fake_post.calls == 3
    assert len(no_sleep) == 2


def test_openai_provider_stops_retrying_after_configured_attempts(monkeypatch, no_sleep):
    fake_post = _CallCountingPost(failures_then_success=None, failure_status=500)
    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small", max_retries=2)

    with pytest.raises(EmbeddingProviderError, match="OpenAI embedding request failed"):
        provider.embed(["hello"])

    # 1 initial attempt + 2 retries = 3 calls total, exactly max_retries + 1
    assert fake_post.calls == 3
    assert len(no_sleep) == 2


def test_openai_provider_retries_rate_limit_429(monkeypatch, no_sleep):
    fake_post = _CallCountingPost(failures_then_success=1, failure_status=429)
    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small", max_retries=3)

    result = provider.embed(["hello"])

    assert result == [[0.1, 0.1]]
    assert fake_post.calls == 2


def test_openai_provider_does_not_retry_bad_request(monkeypatch, no_sleep):
    fake_post = _CallCountingPost(failures_then_success=None, failure_status=400)
    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small", max_retries=3)

    with pytest.raises(EmbeddingProviderError, match="OpenAI embedding request failed"):
        provider.embed(["hello"])

    assert fake_post.calls == 1
    assert len(no_sleep) == 0


def test_openai_provider_does_not_retry_authentication_failure(monkeypatch, no_sleep):
    fake_post = _CallCountingPost(failures_then_success=None, failure_status=401)
    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small", max_retries=3)

    with pytest.raises(EmbeddingProviderError, match="OpenAI embedding request failed"):
        provider.embed(["hello"])

    assert fake_post.calls == 1
    assert len(no_sleep) == 0


def test_openai_provider_does_not_retry_forbidden(monkeypatch, no_sleep):
    fake_post = _CallCountingPost(failures_then_success=None, failure_status=403)
    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small", max_retries=3)

    with pytest.raises(EmbeddingProviderError, match="OpenAI embedding request failed"):
        provider.embed(["hello"])

    assert fake_post.calls == 1
    assert len(no_sleep) == 0


def test_openai_provider_retry_count_is_configurable(monkeypatch, no_sleep):
    fake_post = _CallCountingPost(failures_then_success=None, failure_status=500)
    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small", max_retries=0)

    with pytest.raises(EmbeddingProviderError):
        provider.embed(["hello"])

    # max_retries=0 means exactly one attempt, no retries at all
    assert fake_post.calls == 1
    assert len(no_sleep) == 0


def test_openai_provider_backoff_delay_is_exponential_and_configurable(monkeypatch, no_sleep):
    fake_post = _CallCountingPost(failures_then_success=None, failure_status=500)
    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAIEmbeddingProvider(
        api_key="test-key", model="text-embedding-3-small", max_retries=3, base_delay_seconds=0.25
    )

    with pytest.raises(EmbeddingProviderError):
        provider.embed(["hello"])

    assert no_sleep == [0.25, 0.5, 1.0]


def test_openai_provider_defaults_to_three_retries_and_half_second_base_delay():
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")

    assert provider.max_retries == 3
    assert provider.base_delay_seconds == 0.5


# --- metrics (Task 2) ----------------------------------------------------


class _FakeMetrics:
    def __init__(self):
        self.successes: list[dict] = []
        self.failures: list[dict] = []
        self.retries: list[dict] = []

    def embedding_generation_success(self, **context):
        self.successes.append(context)

    def embedding_generation_failure(self, **context):
        self.failures.append(context)

    def embedding_retry_count(self, attempt, **context):
        self.retries.append({"attempt": attempt, **context})

    def vector_store_success(self, operation, **context):
        pass

    def vector_store_failure(self, operation, **context):
        pass


def test_openai_provider_records_success_metric(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post({"data": [{"index": 0, "embedding": [0.1]}]}))
    metrics = _FakeMetrics()
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small", metrics=metrics)

    provider.embed(["hello"])

    assert len(metrics.successes) == 1
    assert metrics.successes[0]["model"] == "text-embedding-3-small"
    assert len(metrics.failures) == 0


def test_openai_provider_records_failure_metric_for_missing_api_key():
    metrics = _FakeMetrics()
    provider = OpenAIEmbeddingProvider(api_key=None, model="text-embedding-3-small", metrics=metrics)

    with pytest.raises(EmbeddingProviderError):
        provider.embed(["hello"])

    assert len(metrics.failures) == 1
    assert metrics.failures[0]["reason"] == "missing_api_key"


def test_openai_provider_records_failure_metric_for_non_retryable_status(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post({"error": {"message": "bad request"}}, status_code=400))
    metrics = _FakeMetrics()
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small", metrics=metrics)

    with pytest.raises(EmbeddingProviderError):
        provider.embed(["hello"])

    assert len(metrics.failures) == 1
    assert metrics.failures[0]["reason"] == "non_retryable_status"
    assert metrics.failures[0]["status_code"] == 400


def test_openai_provider_records_retry_count_metric(monkeypatch, no_sleep):
    fake_post = _CallCountingPost(failures_then_success=2)
    monkeypatch.setattr(httpx, "post", fake_post)
    metrics = _FakeMetrics()
    provider = OpenAIEmbeddingProvider(
        api_key="test-key", model="text-embedding-3-small", max_retries=3, metrics=metrics
    )

    provider.embed(["hello"])

    assert [r["attempt"] for r in metrics.retries] == [1, 2]
    assert len(metrics.successes) == 1


def test_openai_provider_records_failure_metric_after_retries_exhausted(monkeypatch, no_sleep):
    fake_post = _CallCountingPost(failures_then_success=None, failure_status=500)
    monkeypatch.setattr(httpx, "post", fake_post)
    metrics = _FakeMetrics()
    provider = OpenAIEmbeddingProvider(
        api_key="test-key", model="text-embedding-3-small", max_retries=2, metrics=metrics
    )

    with pytest.raises(EmbeddingProviderError):
        provider.embed(["hello"])

    assert len(metrics.failures) == 1
    assert metrics.failures[0]["reason"] == "retries_exhausted"
    assert metrics.failures[0]["attempts"] == 3


def test_openai_provider_records_failure_metric_for_malformed_response(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post({"unexpected": "shape"}))
    metrics = _FakeMetrics()
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small", metrics=metrics)

    with pytest.raises(EmbeddingProviderError):
        provider.embed(["hello"])

    assert len(metrics.failures) == 1
    assert metrics.failures[0]["reason"] == "malformed_response"


def test_openai_provider_defaults_metrics_via_factory():
    from app.metrics.base_recorder import MetricsRecorder
    from app.metrics.safe_recorder import SafeMetricsRecorder

    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")

    assert isinstance(provider.metrics, MetricsRecorder)
    assert isinstance(provider.metrics, SafeMetricsRecorder)


def test_openai_provider_succeeds_even_when_metrics_recorder_is_broken(monkeypatch):
    """Task 4: observability must never become a production dependency - a
    broken metrics recorder (as MetricsRecorderFactory always hands out,
    wrapped in SafeMetricsRecorder) must not stop embed() from succeeding."""
    from app.metrics.safe_recorder import SafeMetricsRecorder

    class _BrokenRecorder:
        def embedding_generation_success(self, **context):
            raise RuntimeError("metrics backend unreachable")

        def embedding_generation_failure(self, **context):
            raise RuntimeError("metrics backend unreachable")

        def embedding_retry_count(self, attempt, **context):
            raise RuntimeError("metrics backend unreachable")

    monkeypatch.setattr(httpx, "post", _fake_post({"data": [{"index": 0, "embedding": [0.1, 0.2]}]}))
    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        model="text-embedding-3-small",
        metrics=SafeMetricsRecorder(_BrokenRecorder()),
    )

    result = provider.embed(["hello"])

    assert result == [[0.1, 0.2]]
