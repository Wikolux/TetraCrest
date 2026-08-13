from app.services.ai.agents.specialists.shared.metrics import aggregate_metrics
from app.services.ai.kernel.metrics import ExecutionMetrics


def test_aggregate_with_no_metrics_returns_empty_metrics():
    result = aggregate_metrics()

    assert result.latency_ms is None
    assert result.duration_ms is None
    assert result.retry_count == 0


def test_aggregate_ignores_none_entries():
    metrics = ExecutionMetrics(duration_ms=10.0)

    result = aggregate_metrics(None, metrics, None)

    assert result.duration_ms == 10.0


def test_aggregate_sums_latency_and_duration():
    first = ExecutionMetrics(latency_ms=10.0, duration_ms=20.0)
    second = ExecutionMetrics(latency_ms=5.0, duration_ms=15.0)

    result = aggregate_metrics(first, second)

    assert result.latency_ms == 15.0
    assert result.duration_ms == 35.0


def test_aggregate_sums_retry_counts():
    first = ExecutionMetrics(retry_count=2)
    second = ExecutionMetrics(retry_count=3)

    result = aggregate_metrics(first, second)

    assert result.retry_count == 5


def test_aggregate_sets_the_given_execution_id():
    result = aggregate_metrics(ExecutionMetrics(duration_ms=1.0), execution_id="exec-1")

    assert result.execution_id == "exec-1"


def test_aggregate_is_deterministic():
    first = ExecutionMetrics(latency_ms=1.0, duration_ms=2.0, retry_count=1)
    second = ExecutionMetrics(latency_ms=3.0, duration_ms=4.0, retry_count=2)

    result_a = aggregate_metrics(first, second, execution_id="e")
    result_b = aggregate_metrics(first, second, execution_id="e")

    assert result_a == result_b
