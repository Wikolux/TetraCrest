from abc import ABC, abstractmethod


class MetricsRecorder(ABC):
    """Records operational events for the embedding/vector-store subsystem.

    A single abstraction so a real monitoring backend (Prometheus,
    OpenTelemetry, Datadog, ...) can be plugged in later by implementing
    this interface and registering it with MetricsRecorderFactory -
    business logic (OpenAIEmbeddingProvider, PgVectorStore, ...) only ever
    calls these named methods, never a logging call or a vendor SDK
    directly. Swapping the backend never means touching a call site.
    """

    @abstractmethod
    def embedding_generation_success(self, **context) -> None:
        """Record that an embedding was generated successfully."""
        raise NotImplementedError

    @abstractmethod
    def embedding_generation_failure(self, **context) -> None:
        """Record that embedding generation failed (after any retries)."""
        raise NotImplementedError

    @abstractmethod
    def embedding_retry_count(self, attempt: int, **context) -> None:
        """Record that an embedding request is being retried."""
        raise NotImplementedError

    @abstractmethod
    def vector_store_success(self, operation: str, **context) -> None:
        """Record that a vector store operation (save/get/delete/search) succeeded."""
        raise NotImplementedError

    @abstractmethod
    def vector_store_failure(self, operation: str, **context) -> None:
        """Record that a vector store operation (save/get/delete/search) failed."""
        raise NotImplementedError
