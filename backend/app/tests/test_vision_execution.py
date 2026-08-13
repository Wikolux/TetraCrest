import time

import pytest

from app.services.ai.runtime.cancellation import CancellationToken
from app.services.ai.shared.exceptions import AIProviderError
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.vision.events import VisionEventPublisher, VisionEventType
from app.services.ai.vision.execution import VisionExecutor
from app.services.ai.vision.hooks import VisionHook
from app.services.ai.vision.image.base_provider import ImageVisionProvider
from app.services.ai.vision.image.registry import ImageVisionProviderRegistry
from app.services.ai.vision.middleware import VisionMiddleware
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.request import VisionInput, VisionInputKind, VisionRequest
from app.services.ai.vision.response import VisionResponse
from app.services.ai.vision.shared.types import DetectedObject, ExtractedTable, ExtractedText


class _FakeProvider:
    """Exposes all four capability verbs (describe/understand/extract/
    analyze) delegating to one shared implementation, so the same fake can
    back whichever capability_category a given test targets."""

    def __init__(self, *, result=None, raises=None, delay=0.0):
        self.result = result if result is not None else VisionResponse(success=True)
        self.raises = raises
        self.delay = delay
        self.calls = []

    def _invoke(self, request):
        self.calls.append(request)
        if self.delay:
            time.sleep(self.delay)
        if self.raises is not None:
            raise self.raises
        return self.result

    def describe(self, request):
        return self._invoke(request)

    def understand(self, request):
        return self._invoke(request)

    def extract(self, request):
        return self._invoke(request)

    def analyze(self, request):
        return self._invoke(request)


class _FlakyProvider(_FakeProvider):
    def __init__(self, fail_times, **kwargs):
        super().__init__(**kwargs)
        self.fail_times = fail_times
        self.attempts = 0

    def _invoke(self, request):
        self.attempts += 1
        self.calls.append(request)
        if self.attempts <= self.fail_times:
            raise ValueError("transient failure")
        return self.result


class _BadReturnProvider(_FakeProvider):
    def _invoke(self, request):
        self.calls.append(request)
        return "not a VisionResponse"


class _RecordingHook(VisionHook):
    def __init__(self):
        self.calls: list[tuple] = []

    def before_analysis(self, context, request):
        self.calls.append(("before_analysis",))

    def after_analysis(self, context, response):
        self.calls.append(("after_analysis", response.success))

    def on_failure(self, context, error):
        self.calls.append(("on_failure", str(error)))

    def on_timeout(self, context):
        self.calls.append(("on_timeout",))

    def on_cancel(self, context):
        self.calls.append(("on_cancel",))


def _request(**overrides):
    defaults = dict(
        inputs=(VisionInput(kind=VisionInputKind.IMAGE, bytes_data=b"x"),),
        capability_category="image",
    )
    defaults.update(overrides)
    return VisionRequest(**defaults)


def _event_types(events):
    return [event.event_type for event in events]


def _executor_with_events(provider_factory, *, category="image", **kwargs):
    events = []
    publisher = VisionEventPublisher()
    publisher.subscribe(events.append)
    executor = VisionExecutor(
        event_publisher=publisher, provider_factory_map={category: provider_factory}, **kwargs
    )
    return executor, events


# --- successful execution --------------------------------------------------------------


def test_successful_execution_returns_a_success_response():
    provider = _FakeProvider(result=VisionResponse(success=True, confidence=0.9))
    executor, events = _executor_with_events(lambda name, config: provider)

    response = executor.execute(_request())

    assert response.success is True
    assert response.confidence == 0.9


def test_successful_image_execution_emits_events_in_order():
    provider = _FakeProvider()
    executor, events = _executor_with_events(lambda name, config: provider)

    executor.execute(_request())

    assert _event_types(events) == [VisionEventType.VISION_STARTED, VisionEventType.IMAGE_ANALYZED, VisionEventType.VISION_COMPLETED]


def test_document_capability_emits_document_analyzed():
    provider = _FakeProvider()
    executor, events = _executor_with_events(lambda name, config: provider, category="document")

    executor.execute(_request(capability_category="document"))

    assert VisionEventType.DOCUMENT_ANALYZED in _event_types(events)


def test_content_driven_events_are_emitted_when_populated():
    response = VisionResponse(
        success=True,
        extracted_text=(ExtractedText(content="hi"),),
        tables=(ExtractedTable(),),
        objects=(DetectedObject(label="cat"),),
    )
    provider = _FakeProvider(result=response)
    executor, events = _executor_with_events(lambda name, config: provider)

    executor.execute(_request())

    types = _event_types(events)
    assert VisionEventType.TEXT_EXTRACTED in types
    assert VisionEventType.TABLE_EXTRACTED in types
    assert VisionEventType.OBJECTS_DETECTED in types


def test_content_driven_events_are_not_emitted_when_empty():
    provider = _FakeProvider(result=VisionResponse(success=True))
    executor, events = _executor_with_events(lambda name, config: provider)

    executor.execute(_request())

    types = _event_types(events)
    assert VisionEventType.TEXT_EXTRACTED not in types
    assert VisionEventType.TABLE_EXTRACTED not in types
    assert VisionEventType.OBJECTS_DETECTED not in types


def test_every_event_carries_execution_id_and_correlation_id():
    provider = _FakeProvider()
    executor, events = _executor_with_events(lambda name, config: provider)

    response = executor.execute(_request())

    assert all(event.execution_id == response.execution_id for event in events)
    assert all(event.correlation_id == response.correlation_id for event in events)


def test_hooks_fire_before_and_after_analysis_on_success():
    hook = _RecordingHook()
    provider = _FakeProvider()
    executor = VisionExecutor(hooks=(hook,), provider_factory_map={"image": lambda name, config: provider})

    executor.execute(_request())

    assert hook.calls == [("before_analysis",), ("after_analysis", True)]


# --- identity / metrics propagation --------------------------------------------------------


def test_response_identity_matches_event_identity():
    provider = _FakeProvider()
    executor, events = _executor_with_events(lambda name, config: provider)

    response = executor.execute(_request())

    assert {event.execution_id for event in events} == {response.execution_id}


def test_metrics_are_populated():
    provider = _FakeProvider()
    executor = VisionExecutor(provider_factory_map={"image": lambda name, config: provider})

    response = executor.execute(_request())

    assert response.metrics is not None
    assert response.metrics.execution_id == response.execution_id
    assert response.metrics.duration_ms >= 0
    assert response.duration_ms == response.metrics.duration_ms


def test_a_request_with_no_parent_shared_starts_its_own_correlation_chain():
    provider = _FakeProvider()
    executor = VisionExecutor(provider_factory_map={"image": lambda name, config: provider})

    response = executor.execute(_request())

    assert response.correlation_id == response.execution_id


def test_response_carries_correlation_and_parent_from_the_requests_parent_shared():
    parent_shared = SharedExecutionContext(organization_id=1)
    provider = _FakeProvider()
    executor = VisionExecutor(provider_factory_map={"image": lambda name, config: provider})

    response = executor.execute(_request(parent_shared=parent_shared))

    assert response.correlation_id == parent_shared.correlation_id
    assert response.parent_execution_id == parent_shared.execution_id
    assert response.execution_id != parent_shared.execution_id


# --- provider resolution failure (not retryable) ------------------------------------------


def test_provider_resolution_failure_is_reported_as_a_failed_response():
    def _factory(name, config):
        raise AIProviderError("unresolved")

    executor = VisionExecutor(provider_factory_map={"image": _factory}, max_retries=3)

    response = executor.execute(_request())

    assert response.success is False
    assert "unresolved" in response.error


def test_provider_resolution_failure_is_never_retried():
    calls = []

    def _factory(name, config):
        calls.append(1)
        raise AIProviderError("unresolved")

    executor = VisionExecutor(provider_factory_map={"image": _factory}, max_retries=3)

    executor.execute(_request())

    assert len(calls) == 1


# --- generic failure (retryable) -----------------------------------------------------------


def test_default_max_retries_is_zero():
    provider = _FlakyProvider(fail_times=1)
    executor = VisionExecutor(provider_factory_map={"image": lambda name, config: provider})

    response = executor.execute(_request())

    assert response.success is False
    assert provider.attempts == 1


def test_generic_failure_is_retried_and_can_eventually_succeed():
    provider = _FlakyProvider(fail_times=2)
    executor = VisionExecutor(provider_factory_map={"image": lambda name, config: provider}, max_retries=2)

    response = executor.execute(_request())

    assert response.success is True
    assert provider.attempts == 3
    assert response.metrics.retry_count == 2


def test_generic_failure_exhausts_retries_and_reports_failure():
    provider = _FlakyProvider(fail_times=5)
    executor = VisionExecutor(provider_factory_map={"image": lambda name, config: provider}, max_retries=2)

    response = executor.execute(_request())

    assert response.success is False
    assert provider.attempts == 3
    assert "transient failure" in response.error


def test_on_failure_hook_fires_for_a_generic_exception():
    hook = _RecordingHook()
    provider = _FlakyProvider(fail_times=1)
    executor = VisionExecutor(hooks=(hook,), provider_factory_map={"image": lambda name, config: provider})

    executor.execute(_request())

    assert ("on_failure", "transient failure") in hook.calls


# --- provider contract violation -------------------------------------------------------------


def test_a_provider_that_does_not_return_a_vision_response_is_reported_as_a_failure():
    provider = _BadReturnProvider()
    executor = VisionExecutor(provider_factory_map={"image": lambda name, config: provider})

    response = executor.execute(_request())

    assert response.success is False
    assert "VisionResponse" in response.error


# --- unknown capability -----------------------------------------------------------------------


def test_unknown_capability_category_fails_immediately():
    executor = VisionExecutor()

    response = executor.execute(_request(capability_category="unknown-category"))

    assert response.success is False
    assert "Unknown capability_category" in response.error


# --- cancellation ------------------------------------------------------------------------------


def test_cancellation_before_start_prevents_any_provider_call():
    token = CancellationToken()
    token.cancel()
    provider = _FakeProvider()
    executor, events = _executor_with_events(lambda name, config: provider)

    response = executor.execute(_request(cancellation_token=token))

    assert response.success is False
    assert "cancelled" in response.error.lower()
    assert provider.calls == []


def test_on_cancel_hook_fires_when_cancelled_before_start():
    hook = _RecordingHook()
    token = CancellationToken()
    token.cancel()
    provider = _FakeProvider()
    executor = VisionExecutor(hooks=(hook,), provider_factory_map={"image": lambda name, config: provider})

    executor.execute(_request(cancellation_token=token))

    assert ("on_cancel",) in hook.calls


def test_cancellation_is_checked_between_retry_attempts():
    token = CancellationToken()

    class _CancelingProvider(_FakeProvider):
        def describe(self, request):
            self.calls.append(request)
            token.cancel()
            raise ValueError("boom")

    provider = _CancelingProvider()
    executor = VisionExecutor(provider_factory_map={"image": lambda name, config: provider}, max_retries=3)

    response = executor.execute(_request(cancellation_token=token))

    assert len(provider.calls) == 1
    assert response.success is False


# --- middleware integration ------------------------------------------------------------------


def test_middleware_wraps_the_provider_invocation():
    log = []

    class _LoggingMiddleware(VisionMiddleware):
        def __call__(self, context, provider, call_next):
            log.append("before")
            result = call_next(context, provider)
            log.append("after")
            return result

    provider = _FakeProvider()
    executor = VisionExecutor(
        middleware=(_LoggingMiddleware(),), provider_factory_map={"image": lambda name, config: provider}
    )

    executor.execute(_request())

    assert log == ["before", "after"]


def test_middleware_can_short_circuit_and_skip_the_provider():
    class _BlockingMiddleware(VisionMiddleware):
        def __call__(self, context, provider, call_next):
            return VisionResponse(success=False, error="blocked by middleware")

    provider = _FakeProvider()
    executor = VisionExecutor(
        middleware=(_BlockingMiddleware(),), provider_factory_map={"image": lambda name, config: provider}
    )

    response = executor.execute(_request())

    assert response.success is False
    assert response.error == "blocked by middleware"
    assert provider.calls == []


# --- determinism / no mutation ------------------------------------------------------------------


def test_execution_does_not_mutate_the_request():
    provider = _FakeProvider()
    executor = VisionExecutor(provider_factory_map={"image": lambda name, config: provider})
    request = _request()

    executor.execute(request)

    assert request.capability_category == "image"
    assert len(request.inputs) == 1


def test_execution_is_deterministic_for_equivalent_requests():
    provider_a = _FakeProvider(result=VisionResponse(success=True, confidence=0.5))
    provider_b = _FakeProvider(result=VisionResponse(success=True, confidence=0.5))
    executor_a = VisionExecutor(provider_factory_map={"image": lambda name, config: provider_a})
    executor_b = VisionExecutor(provider_factory_map={"image": lambda name, config: provider_b})

    response_a = executor_a.execute(_request())
    response_b = executor_b.execute(_request())

    assert response_a.success == response_b.success
    assert response_a.confidence == response_b.confidence


# --- real registry/factory integration (default provider_factory_map) --------------------------


class _RegisteredImageProvider(ImageVisionProvider):
    def __init__(self, config=None):
        self.config = config

    def describe(self, request):
        return VisionResponse(success=True, confidence=0.42)

    def health_check(self):
        return True

    @property
    def provider_name(self):
        return ProviderName.OPENAI

    @property
    def model_name(self):
        return "fake-registered-vision"


@pytest.fixture
def _isolated_image_registry():
    original = dict(ImageVisionProviderRegistry._providers)
    ImageVisionProviderRegistry._providers.clear()
    yield
    ImageVisionProviderRegistry._providers.clear()
    ImageVisionProviderRegistry._providers.update(original)


def test_default_provider_factory_map_resolves_through_the_real_image_registry(_isolated_image_registry):
    ImageVisionProviderRegistry.register(ProviderName.OPENAI, _RegisteredImageProvider)
    executor = VisionExecutor()

    response = executor.execute(_request(provider=ProviderName.OPENAI))

    assert response.success is True
    assert response.confidence == 0.42


def test_default_provider_factory_map_reports_ai_provider_error_for_an_unregistered_provider(
    _isolated_image_registry,
):
    executor = VisionExecutor()

    response = executor.execute(_request(provider=ProviderName.OPENAI))

    assert response.success is False
    assert "Unsupported image_vision provider" in response.error
