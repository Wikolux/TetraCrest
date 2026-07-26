import time

import httpx

from app.metrics.base_recorder import MetricsRecorder
from app.metrics.recorder_factory import MetricsRecorderFactory
from app.services.embedding.base_provider import EmbeddingProvider, EmbeddingProviderError

EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
REQUEST_TIMEOUT_SECONDS = 30.0

# 4xx codes that mean "this request will never succeed" - retrying wastes
# time and (for auth) risks looking like credential-stuffing. Everything
# else 4xx-and-up not in this set is treated as transient (429 rate limits,
# 408 timeouts, 5xx server errors) and retried.
_NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by OpenAI's /v1/embeddings API.

    Talks to the API directly over HTTP (no `openai` SDK dependency), the
    same way URLIngestor talks to arbitrary web pages - a plain httpx call
    with errors translated into a domain-specific exception.

    Retries transient failures (connection errors, timeouts, 429/5xx) with
    exponential backoff, entirely internally - callers only ever see a
    successful result or an EmbeddingProviderError once retries (if any)
    are exhausted. No caller needs to know retries happened.

    Reports every outcome (success, failure, each retry) through
    MetricsRecorder in addition to raising/returning normally - metrics are
    for observability dashboards, the return value/exception is what
    callers actually react to.
    """

    def __init__(
        self,
        api_key: str | None,
        model: str,
        max_retries: int = 3,
        base_delay_seconds: float = 0.5,
        metrics: MetricsRecorder | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self.metrics = metrics or MetricsRecorderFactory.create()

    @property
    def model_name(self) -> str:
        return self.model

    def health_check(self) -> bool:
        """Report whether an API key is configured.

        Deliberately does not make a real request - OpenAI has no free
        "ping" endpoint, and spending a billed embedding call on a health
        check isn't appropriate.
        """
        return bool(self.api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            self.metrics.embedding_generation_failure(reason="missing_api_key", model=self.model)
            raise EmbeddingProviderError("OpenAI API key is not configured")
        if not texts:
            return []

        last_exc: httpx.HTTPError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = httpx.post(
                    EMBEDDINGS_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "input": texts},
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in _NON_RETRYABLE_STATUS_CODES:
                    self.metrics.embedding_generation_failure(
                        reason="non_retryable_status",
                        status_code=exc.response.status_code,
                        model=self.model,
                    )
                    raise EmbeddingProviderError(f"OpenAI embedding request failed: {exc}") from exc
                last_exc = exc
            except httpx.HTTPError as exc:
                last_exc = exc
            else:
                try:
                    parsed = self._parse_embeddings(response)
                except EmbeddingProviderError:
                    self.metrics.embedding_generation_failure(reason="malformed_response", model=self.model)
                    raise
                self.metrics.embedding_generation_success(attempts=attempt + 1, model=self.model)
                return parsed

            if attempt < self.max_retries:
                self.metrics.embedding_retry_count(attempt=attempt + 1, model=self.model)
                time.sleep(self.base_delay_seconds * (2**attempt))

        self.metrics.embedding_generation_failure(
            reason="retries_exhausted", attempts=self.max_retries + 1, model=self.model
        )
        raise EmbeddingProviderError(f"OpenAI embedding request failed: {last_exc}") from last_exc

    @staticmethod
    def _parse_embeddings(response: httpx.Response) -> list[list[float]]:
        payload = response.json()
        try:
            ordered = sorted(payload["data"], key=lambda item: item["index"])
            return [item["embedding"] for item in ordered]
        except (KeyError, TypeError) as exc:
            raise EmbeddingProviderError("OpenAI embedding response was malformed") from exc
