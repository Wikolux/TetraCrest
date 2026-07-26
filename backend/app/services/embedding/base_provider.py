from abc import ABC, abstractmethod


class EmbeddingProviderError(Exception):
    """Raised when an embedding provider fails to produce embeddings.

    Callers (EmbeddingService and, later, whatever calls it) catch this
    single type regardless of which concrete provider is configured, so a
    provider outage never surfaces as an unhandled SDK/HTTP exception.
    """


class EmbeddingProvider(ABC):
    """Common contract for every embedding backend.

    A concrete provider turns text into vectors however its backend
    requires (a hosted HTTP API, a local model, ...). EmbeddingService
    depends only on this interface, so adding a new backend - Azure OpenAI,
    VoyageAI, Cohere, a local model - never means changing the service or
    its callers.
    """

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, in the same order."""
        raise NotImplementedError

    def health_check(self) -> bool:
        """Return whether this provider is configured and able to serve requests.

        Concrete (not abstract) with an optimistic default so existing and
        future providers aren't forced to implement it; override when a
        provider has something meaningful and cheap to check (e.g. an API
        key being present) without spending a real embedding call on it.
        """
        return True

    @property
    def model_name(self) -> str:
        """Return the identifier of the embedding model this provider uses.

        Concrete (not abstract) with a generic default so existing/future
        providers aren't forced to implement it; override to return the
        real model identifier (e.g. "text-embedding-3-small") so
        EmbeddingPersistenceService can record which model produced each
        stored vector - important later for migrations/re-indexing when
        multiple models' vectors coexist.
        """
        return "unknown"
