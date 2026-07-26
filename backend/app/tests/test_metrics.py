from app.metrics.base_recorder import MetricsRecorder
from app.metrics.logging_recorder import LoggingMetricsRecorder
from app.metrics.safe_recorder import SafeMetricsRecorder


class _CapturingLogger:
    def __init__(self):
        self.records: list[tuple[str, dict]] = []

    def info(self, message, extra=None):
        self.records.append((message, extra or {}))


def _recorder_with_capturing_logger() -> tuple[LoggingMetricsRecorder, _CapturingLogger]:
    recorder = LoggingMetricsRecorder()
    fake_logger = _CapturingLogger()
    recorder._logger = fake_logger
    return recorder, fake_logger


def test_logging_metrics_recorder_implements_the_interface():
    assert isinstance(LoggingMetricsRecorder(), MetricsRecorder)


def test_embedding_generation_success_is_logged():
    recorder, logger = _recorder_with_capturing_logger()

    recorder.embedding_generation_success(model="text-embedding-3-small", attempts=1)

    message, extra = logger.records[0]
    assert message == "embedding_generation_success"
    assert extra["metric"] == "embedding_generation_success"
    assert extra["model"] == "text-embedding-3-small"
    assert extra["attempts"] == 1


def test_embedding_generation_failure_is_logged():
    recorder, logger = _recorder_with_capturing_logger()

    recorder.embedding_generation_failure(reason="retries_exhausted", model="text-embedding-3-small")

    message, extra = logger.records[0]
    assert message == "embedding_generation_failure"
    assert extra["metric"] == "embedding_generation_failure"
    assert extra["reason"] == "retries_exhausted"


def test_embedding_retry_count_is_logged():
    recorder, logger = _recorder_with_capturing_logger()

    recorder.embedding_retry_count(attempt=2, model="text-embedding-3-small")

    message, extra = logger.records[0]
    assert message == "embedding_retry_count"
    assert extra["attempt"] == 2


def test_vector_store_success_is_logged():
    recorder, logger = _recorder_with_capturing_logger()

    recorder.vector_store_success(operation="save_vector", vector_id="memory:1")

    message, extra = logger.records[0]
    assert message == "vector_store_success"
    assert extra["operation"] == "save_vector"
    assert extra["vector_id"] == "memory:1"


def test_vector_store_failure_is_logged():
    recorder, logger = _recorder_with_capturing_logger()

    recorder.vector_store_failure(operation="get_vector", vector_id="memory:1")

    message, extra = logger.records[0]
    assert message == "vector_store_failure"
    assert extra["operation"] == "get_vector"


# --- SafeMetricsRecorder (Task 4: recorder failures must never propagate) --


class _AlwaysRaisingRecorder(MetricsRecorder):
    def embedding_generation_success(self, **context):
        raise RuntimeError("boom")

    def embedding_generation_failure(self, **context):
        raise RuntimeError("boom")

    def embedding_retry_count(self, attempt, **context):
        raise RuntimeError("boom")

    def vector_store_success(self, operation, **context):
        raise RuntimeError("boom")

    def vector_store_failure(self, operation, **context):
        raise RuntimeError("boom")


def test_safe_recorder_implements_the_interface():
    assert isinstance(SafeMetricsRecorder(LoggingMetricsRecorder()), MetricsRecorder)


def test_safe_recorder_swallows_embedding_generation_success_failure():
    safe = SafeMetricsRecorder(_AlwaysRaisingRecorder())

    safe.embedding_generation_success(model="x")  # must not raise


def test_safe_recorder_swallows_embedding_generation_failure_failure():
    safe = SafeMetricsRecorder(_AlwaysRaisingRecorder())

    safe.embedding_generation_failure(reason="x")  # must not raise


def test_safe_recorder_swallows_embedding_retry_count_failure():
    safe = SafeMetricsRecorder(_AlwaysRaisingRecorder())

    safe.embedding_retry_count(attempt=1)  # must not raise


def test_safe_recorder_swallows_vector_store_success_failure():
    safe = SafeMetricsRecorder(_AlwaysRaisingRecorder())

    safe.vector_store_success(operation="save_vector")  # must not raise


def test_safe_recorder_swallows_vector_store_failure_failure():
    safe = SafeMetricsRecorder(_AlwaysRaisingRecorder())

    safe.vector_store_failure(operation="save_vector")  # must not raise


def test_safe_recorder_delegates_successfully_to_a_working_recorder():
    recorder, logger = _recorder_with_capturing_logger()
    safe = SafeMetricsRecorder(recorder)

    safe.embedding_generation_success(model="text-embedding-3-small")

    assert logger.records[0][0] == "embedding_generation_success"
