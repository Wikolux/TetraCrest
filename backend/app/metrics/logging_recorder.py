from app.logging_utils import get_logger
from app.metrics.base_recorder import MetricsRecorder


class LoggingMetricsRecorder(MetricsRecorder):
    """Default MetricsRecorder: logs every event as a structured record.

    Sufficient today for debugging/observability via logs. Swapping to a
    real metrics backend later means writing one new MetricsRecorder
    implementation, not touching any of the call sites that already
    depend only on the MetricsRecorder interface.
    """

    def __init__(self):
        self._logger = get_logger("metrics")

    def _log(self, event: str, **context) -> None:
        self._logger.info(event, extra={"metric": event, **context})

    def embedding_generation_success(self, **context) -> None:
        self._log("embedding_generation_success", **context)

    def embedding_generation_failure(self, **context) -> None:
        self._log("embedding_generation_failure", **context)

    def embedding_retry_count(self, attempt: int, **context) -> None:
        self._log("embedding_retry_count", attempt=attempt, **context)

    def vector_store_success(self, operation: str, **context) -> None:
        self._log("vector_store_success", operation=operation, **context)

    def vector_store_failure(self, operation: str, **context) -> None:
        self._log("vector_store_failure", operation=operation, **context)
