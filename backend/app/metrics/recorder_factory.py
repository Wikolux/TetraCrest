from app.core.enums import MetricsRecorderName
from app.metrics.base_recorder import MetricsRecorder
from app.metrics.logging_recorder import LoggingMetricsRecorder
from app.metrics.safe_recorder import SafeMetricsRecorder
from settings import Settings, get_settings

_RECORDERS = {
    MetricsRecorderName.LOGGING: lambda settings: LoggingMetricsRecorder(),
}


class MetricsRecorderFactory:
    """Resolves settings.metrics_recorder_provider into a concrete MetricsRecorder.

    Mirrors EmbeddingProviderFactory and VectorStoreFactory: the only place
    in the codebase that knows which recorder names exist and how each one
    is constructed. Adding a new backend (Prometheus, OpenTelemetry,
    Datadog) means adding one entry here, nothing else - no caller needs
    to know which recorder it receives.

    Deliberately does not fail fast on an unrecognized provider name the
    way the other two factories do. EmbeddingProviderFactory and
    VectorStoreFactory guard genuine business dependencies - you cannot
    generate embeddings or store vectors without one, so misconfiguration
    should be caught immediately. Metrics are purely observational:
    observability must never become a production dependency, so an
    unrecognized metrics_recorder_provider falls back to the default
    recorder instead of raising and blocking provider/store construction.

    Every recorder returned is wrapped in SafeMetricsRecorder, so a bug in
    whichever concrete recorder is configured can never propagate into
    embedding generation or vector storage either.
    """

    @staticmethod
    def create(settings: Settings | None = None) -> MetricsRecorder:
        settings = settings or get_settings()
        build = _RECORDERS.get(settings.metrics_recorder_provider)
        recorder = build(settings) if build is not None else LoggingMetricsRecorder()
        return SafeMetricsRecorder(recorder)
