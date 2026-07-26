import httpx

from app.services.embedding.base_provider import EmbeddingProvider, EmbeddingProviderError

EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
REQUEST_TIMEOUT_SECONDS = 30.0


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by OpenAI's /v1/embeddings API.

    Talks to the API directly over HTTP (no `openai` SDK dependency), the
    same way URLIngestor talks to arbitrary web pages - a plain httpx call
    with errors translated into a domain-specific exception.
    """

    def __init__(self, api_key: str | None, model: str):
        self.api_key = api_key
        self.model = model

    def health_check(self) -> bool:
        """Report whether an API key is configured.

        Deliberately does not make a real request - OpenAI has no free
        "ping" endpoint, and spending a billed embedding call on a health
        check isn't appropriate.
        """
        return bool(self.api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise EmbeddingProviderError("OpenAI API key is not configured")
        if not texts:
            return []

        try:
            response = httpx.post(
                EMBEDDINGS_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingProviderError(f"OpenAI embedding request failed: {exc}") from exc

        payload = response.json()
        try:
            ordered = sorted(payload["data"], key=lambda item: item["index"])
            return [item["embedding"] for item in ordered]
        except (KeyError, TypeError) as exc:
            raise EmbeddingProviderError("OpenAI embedding response was malformed") from exc
