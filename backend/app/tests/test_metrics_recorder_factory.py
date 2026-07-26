from app.metrics.logging_recorder import LoggingMetricsRecorder
from app.metrics.recorder_factory import MetricsRecorderFactory
from app.metrics.safe_recorder import SafeMetricsRecorder
from settings import get_settings


def test_factory_returns_a_safe_wrapped_logging_recorder_by_default(monkeypatch):
    monkeypatch.setenv("METRICS_RECORDER_PROVIDER", "logging")
    get_settings.cache_clear()

    try:
        recorder = MetricsRecorderFactory.create()
        assert isinstance(recorder, SafeMetricsRecorder)
        assert isinstance(recorder._delegate, LoggingMetricsRecorder)
    finally:
        get_settings.cache_clear()


def test_factory_falls_back_to_default_recorder_for_unsupported_provider(monkeypatch):
    # Unlike EmbeddingProviderFactory/VectorStoreFactory, an unrecognized
    # metrics_recorder_provider must never raise - observability is not
    # allowed to become a business-critical dependency.
    monkeypatch.setenv("METRICS_RECORDER_PROVIDER", "not-a-real-recorder")
    get_settings.cache_clear()

    try:
        recorder = MetricsRecorderFactory.create()
        assert isinstance(recorder, SafeMetricsRecorder)
        assert isinstance(recorder._delegate, LoggingMetricsRecorder)
    finally:
        get_settings.cache_clear()


def test_factory_accepts_explicit_settings_instead_of_global():
    settings = get_settings().model_copy(update={"metrics_recorder_provider": "logging"})

    recorder = MetricsRecorderFactory.create(settings)

    assert isinstance(recorder, SafeMetricsRecorder)
    assert isinstance(recorder._delegate, LoggingMetricsRecorder)


def test_factory_returns_a_new_instance_each_call():
    # No process-wide singleton anymore - every caller gets its own
    # recorder instance, resolved fresh through the factory each time.
    first = MetricsRecorderFactory.create()
    second = MetricsRecorderFactory.create()

    assert first is not second
