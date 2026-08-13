"""aggregate_metrics - combines multiple ExecutionMetrics (one per tool
call, one for the runtime call, ...) into a single ExecutionMetrics for a
SpecialistResponse. Does not redefine the metrics type itself - "Do NOT
duplicate any subsystem" applies to aggregation the same way it applies
to everything else this framework reuses.
"""

from app.services.ai.kernel.metrics import ExecutionMetrics


def aggregate_metrics(*metrics: ExecutionMetrics | None, execution_id: str | None = None) -> ExecutionMetrics:
    present = [metric for metric in metrics if metric is not None]

    latencies = [metric.latency_ms for metric in present if metric.latency_ms is not None]
    durations = [metric.duration_ms for metric in present if metric.duration_ms is not None]

    return ExecutionMetrics(
        latency_ms=sum(latencies) if latencies else None,
        duration_ms=sum(durations) if durations else None,
        retry_count=sum(metric.retry_count for metric in present),
        execution_id=execution_id,
    )
