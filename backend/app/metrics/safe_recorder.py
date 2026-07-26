from app.logging_utils import get_logger
from app.metrics.base_recorder import MetricsRecorder

logger = get_logger("metrics.safety")


class SafeMetricsRecorder(MetricsRecorder):
    """Wraps another MetricsRecorder so its failures never propagate.

    Observability must never become a production dependency: if a
    recorder implementation (today's LoggingMetricsRecorder, or a future
    Prometheus/OTel/Datadog client) raises - a bad network call, a
    misconfigured exporter, anything - that must not break embedding
    generation or vector storage. MetricsRecorderFactory always returns an
    instance wrapped in this, so OpenAIEmbeddingProvider and PgVectorStore
    never need their own defensive try/except around a metrics call.
    """

    def __init__(self, delegate: MetricsRecorder):
        self._delegate = delegate

    def _safe_call(self, method_name: str, *args, **kwargs) -> None:
        try:
            getattr(self._delegate, method_name)(*args, **kwargs)
        except Exception:
            logger.warning(f"metrics_recorder_failed:{method_name}", exc_info=True)

    def embedding_generation_success(self, **context) -> None:
        self._safe_call("embedding_generation_success", **context)

    def embedding_generation_failure(self, **context) -> None:
        self._safe_call("embedding_generation_failure", **context)

    def embedding_retry_count(self, attempt: int, **context) -> None:
        self._safe_call("embedding_retry_count", attempt, **context)

    def vector_store_success(self, operation: str, **context) -> None:
        self._safe_call("vector_store_success", operation, **context)

    def vector_store_failure(self, operation: str, **context) -> None:
        self._safe_call("vector_store_failure", operation, **context)
