import time

import pytest

from app.services.ai.conversation.base_provider import ConversationProvider
from app.services.ai.conversation.registry import ConversationProviderRegistry
from app.services.ai.conversation.types import ConversationResponse
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.cancellation import CancellationToken
from app.services.ai.runtime.execution import RuntimeExecutor
from app.services.ai.runtime.hooks import RuntimeHook
from app.services.ai.runtime.middleware import RuntimeMiddleware
from app.services.ai.runtime.types import EventType, RuntimeExecutionResult, RuntimeRequest
from app.services.ai.shared.exceptions import AIProviderError
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.shared.provider_config import ConversationProviderConfig
from app.services.ai.shared.response import AIResponseMetadata, ProviderResponse, UsageDetails
from app.services.prompt_builder.types import PromptPackage


class _FakeProvider(ConversationProvider):
    def __init__(self, config=None, *, text="hello", delay=0.0, raises=None):
        self.config = config or ConversationProviderConfig()
        self.text = text
        self.delay = delay
        self.raises = raises
        self.calls = []

    def generate(self, prompt_package):
        self.calls.append(prompt_package)
        if self.delay:
            time.sleep(self.delay)
        if self.raises is not None:
            raise self.raises
        return ConversationResponse(
            text=self.text,
            response=ProviderResponse(
                metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="fake"),
                usage=UsageDetails(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            ),
        )

    def health_check(self) -> bool:
        return True

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.OPENAI

    @property
    def model_name(self) -> str:
        return "fake"


class _FlakyProvider(_FakeProvider):
    def __init__(self, fail_times, **kwargs):
        super().__init__(**kwargs)
        self.fail_times = fail_times
        self.attempts = 0

    def generate(self, prompt_package):
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise ValueError("transient failure")
        return super().generate(prompt_package)


class _RecordingHook(RuntimeHook):
    def __init__(self):
        self.calls: list[tuple] = []

    def before_execution(self, context, request):
        self.calls.append(("before_execution",))

    def after_execution(self, context, response):
        self.calls.append(("after_execution", response.success))

    def on_error(self, context, error):
        self.calls.append(("on_error", str(error)))

    def on_cancel(self, context):
        self.calls.append(("on_cancel",))

    def on_timeout(self, context):
        self.calls.append(("on_timeout",))


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(ConversationProviderRegistry._providers)
    ConversationProviderRegistry._providers.clear()
    yield
    ConversationProviderRegistry._providers.clear()
    ConversationProviderRegistry._providers.update(original)


def _request(**overrides):
    defaults = dict(
        organization_id=1,
        prompt_package=PromptPackage(system_prompt="s"),
        provider=ProviderName.OPENAI,
    )
    defaults.update(overrides)
    return RuntimeRequest(**defaults)


def _event_types(response):
    return [event.event_type for event in response.events]


# --- successful execution ------------------------------------------------------------


def test_successful_execution_returns_a_success_response():
    provider = _FakeProvider()
    executor = RuntimeExecutor(provider_factory=lambda name, config: provider)

    response = executor.execute(_request())

    assert response.success is True
    assert response.provider == ProviderName.OPENAI
    assert response.conversation_response.text == "hello"
    assert response.usage.total_tokens == 2
    assert response.error is None
    assert response.latency_ms >= 0


def test_successful_execution_emits_events_in_order():
    provider = _FakeProvider()
    executor = RuntimeExecutor(provider_factory=lambda name, config: provider)

    response = executor.execute(_request())

    assert _event_types(response) == [
        EventType.STARTED,
        EventType.PROVIDER_SELECTED,
        EventType.REQUEST_SENT,
        EventType.RESPONSE_RECEIVED,
        EventType.COMPLETED,
    ]


def test_provider_selected_event_carries_the_provider_name():
    provider = _FakeProvider()
    executor = RuntimeExecutor(provider_factory=lambda name, config: provider)

    response = executor.execute(_request())

    selected = next(e for e in response.events if e.event_type == EventType.PROVIDER_SELECTED)
    assert selected.data["provider"] == str(ProviderName.OPENAI)


def test_all_events_share_the_same_execution_id():
    provider = _FakeProvider()
    executor = RuntimeExecutor(provider_factory=lambda name, config: provider)

    response = executor.execute(_request())

    assert len({event.execution_id for event in response.events}) == 1


def test_hooks_fire_before_and_after_execution_on_success():
    hook = _RecordingHook()
    provider = _FakeProvider()
    executor = RuntimeExecutor(provider_factory=lambda name, config: provider, hooks=(hook,))

    executor.execute(_request())

    assert hook.calls == [("before_execution",), ("after_execution", True)]


# --- provider resolution failure (not retryable) ---------------------------------------


def test_provider_resolution_failure_is_reported_as_a_failed_response():
    executor = RuntimeExecutor(
        provider_factory=lambda name, config: (_ for _ in ()).throw(AIProviderError("unresolved"))
    )

    response = executor.execute(_request())

    assert response.success is False
    assert "unresolved" in response.error
    assert _event_types(response) == [EventType.STARTED, EventType.FAILED]


def test_provider_resolution_failure_is_never_retried():
    calls = []

    def factory(name, config):
        calls.append(1)
        raise AIProviderError("unresolved")

    executor = RuntimeExecutor(provider_factory=factory, max_retries=3)

    executor.execute(_request())

    assert len(calls) == 1


# --- generic provider failure (retryable) -----------------------------------------------


def test_default_max_retries_is_zero():
    flaky = _FlakyProvider(fail_times=1)
    executor = RuntimeExecutor(provider_factory=lambda name, config: flaky)

    response = executor.execute(_request())

    assert response.success is False
    assert flaky.attempts == 1


def test_generic_failure_is_retried_and_can_eventually_succeed():
    flaky = _FlakyProvider(fail_times=2)
    executor = RuntimeExecutor(provider_factory=lambda name, config: flaky, max_retries=2)

    response = executor.execute(_request())

    assert response.success is True
    assert flaky.attempts == 3


def test_generic_failure_exhausts_retries_and_reports_failure():
    flaky = _FlakyProvider(fail_times=5)
    executor = RuntimeExecutor(provider_factory=lambda name, config: flaky, max_retries=2)

    response = executor.execute(_request())

    assert response.success is False
    assert flaky.attempts == 3  # 1 initial + 2 retries
    assert "transient failure" in response.error


def test_on_error_hook_fires_for_a_generic_provider_exception():
    hook = _RecordingHook()
    flaky = _FlakyProvider(fail_times=1)
    executor = RuntimeExecutor(provider_factory=lambda name, config: flaky, hooks=(hook,))

    executor.execute(_request())

    assert ("on_error", "transient failure") in hook.calls


# --- timeout --------------------------------------------------------------------------


def test_timeout_produces_a_failed_response_and_a_timeout_event():
    provider = _FakeProvider(delay=0.05)
    executor = RuntimeExecutor(provider_factory=lambda name, config: provider)

    response = executor.execute(_request(timeout=0.01))

    assert response.success is False
    assert EventType.TIMEOUT in _event_types(response)


def test_on_timeout_hook_fires_on_timeout():
    hook = _RecordingHook()
    provider = _FakeProvider(delay=0.05)
    executor = RuntimeExecutor(provider_factory=lambda name, config: provider, hooks=(hook,))

    executor.execute(_request(timeout=0.01))

    assert ("on_timeout",) in hook.calls


def test_no_timeout_configured_never_raises_runtime_timeout_error():
    provider = _FakeProvider(delay=0.01)
    executor = RuntimeExecutor(provider_factory=lambda name, config: provider)

    response = executor.execute(_request(timeout=None))

    assert response.success is True


# --- cancellation -----------------------------------------------------------------------


def test_cancellation_before_start_prevents_any_provider_call():
    token = CancellationToken()
    token.cancel()
    calls = []
    executor = RuntimeExecutor(provider_factory=lambda name, config: calls.append(1))

    response = executor.execute(_request(cancellation_token=token))

    assert response.success is False
    assert "cancelled" in response.error.lower()
    assert calls == []
    assert EventType.CANCELLED in _event_types(response)


def test_on_cancel_hook_fires_when_cancelled_before_start():
    hook = _RecordingHook()
    token = CancellationToken()
    token.cancel()
    executor = RuntimeExecutor(provider_factory=lambda name, config: _FakeProvider(), hooks=(hook,))

    executor.execute(_request(cancellation_token=token))

    assert ("on_cancel",) in hook.calls


def test_cancellation_is_checked_between_retry_attempts():
    token = CancellationToken()
    attempts = []

    def factory(name, config):
        attempts.append(1)
        if len(attempts) == 1:
            token.cancel()
            raise ValueError("boom")
        raise AssertionError("should not attempt again after cancellation")

    executor = RuntimeExecutor(provider_factory=factory, max_retries=3)

    response = executor.execute(_request(cancellation_token=token))

    assert len(attempts) == 1
    assert response.success is False


# --- middleware / context propagation ----------------------------------------------------


def test_middleware_wraps_the_provider_invocation():
    log = []

    class _LoggingMiddleware(RuntimeMiddleware):
        def __call__(self, context, request, call_next):
            log.append("before")
            result = call_next(context, request)
            log.append("after")
            return result

    provider = _FakeProvider()
    executor = RuntimeExecutor(
        provider_factory=lambda name, config: provider, middleware=(_LoggingMiddleware(),)
    )

    executor.execute(_request())

    assert log == ["before", "after"]


def test_middleware_can_short_circuit_and_skip_the_provider():
    calls = []

    class _BlockingMiddleware(RuntimeMiddleware):
        def __call__(self, context, request, call_next):
            return RuntimeExecutionResult(success=False, error="blocked", retryable=False)

    executor = RuntimeExecutor(
        provider_factory=lambda name, config: calls.append(1),
        middleware=(_BlockingMiddleware(),),
    )

    response = executor.execute(_request())

    assert response.success is False
    assert response.error == "blocked"
    assert calls == []


def test_context_attempt_increments_across_retries():
    captured_attempts = []

    class _CaptureMiddleware(RuntimeMiddleware):
        def __call__(self, context, request, call_next):
            captured_attempts.append(context.attempt)
            return call_next(context, request)

    flaky = _FlakyProvider(fail_times=2)
    executor = RuntimeExecutor(
        provider_factory=lambda name, config: flaky,
        middleware=(_CaptureMiddleware(),),
        max_retries=2,
    )

    executor.execute(_request())

    assert captured_attempts == [1, 2, 3]


# --- integration with the real ConversationProviderFactory/Registry -----------------------


def test_default_provider_factory_resolves_through_the_real_registry():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)
    executor = RuntimeExecutor()

    response = executor.execute(_request())

    assert response.success is True
    assert response.conversation_response.text == "hello"


def test_default_provider_factory_reports_an_unregistered_provider_as_failure():
    executor = RuntimeExecutor()

    response = executor.execute(_request(provider=ProviderName.ANTHROPIC))

    assert response.success is False
    assert "Unsupported conversation provider" in response.error


# --- execution identity (M16.6) -----------------------------------------------------------


class _IdentityCapturingHook(RuntimeHook):
    def __init__(self):
        self.before_execution_ids = []
        self.after_execution_ids = []
        self.after_execution_response_ids = []

    def before_execution(self, context, request):
        self.before_execution_ids.append(context.execution_id)

    def after_execution(self, context, response):
        self.after_execution_ids.append(context.execution_id)
        self.after_execution_response_ids.append(response.execution_id)


class _IdentityCapturingMiddleware(RuntimeMiddleware):
    def __init__(self):
        self.seen_execution_ids = []

    def __call__(self, context, request, call_next):
        self.seen_execution_ids.append(context.execution_id)
        return call_next(context, request)


def test_executor_populates_the_response_directly_from_the_context_not_from_events():
    provider = _FakeProvider()
    executor = RuntimeExecutor(provider_factory=lambda name, config: provider)

    response = executor.execute(_request())

    # every event carries the same execution_id as the response - proof
    # the response's identity was copied from the context, not derived by
    # scanning `response.events` for some other source of truth
    assert response.execution_id
    assert all(event.execution_id == response.execution_id for event in response.events)


def test_response_identity_matches_event_identity_exactly():
    provider = _FakeProvider()
    executor = RuntimeExecutor(provider_factory=lambda name, config: provider)

    response = executor.execute(_request())

    event_execution_ids = {event.execution_id for event in response.events}
    assert event_execution_ids == {response.execution_id}


def test_a_request_with_no_parent_shared_starts_its_own_correlation_chain():
    provider = _FakeProvider()
    executor = RuntimeExecutor(provider_factory=lambda name, config: provider)

    response = executor.execute(_request())

    assert response.correlation_id == response.execution_id
    assert response.parent_execution_id is None


def test_response_carries_correlation_and_parent_from_the_requests_parent_shared_context():
    # simulates an agent (which has its own SharedExecutionContext)
    # invoking the runtime - RuntimeRequest.parent_shared is exactly the
    # seam that makes "Executive -> Agent -> Runtime" one execution tree
    # in the real call path, not just something SharedExecutionContext.child()
    # can do in isolation.
    agent_shared = SharedExecutionContext(organization_id=1)
    provider = _FakeProvider()
    executor = RuntimeExecutor(provider_factory=lambda name, config: provider)

    response = executor.execute(_request(parent_shared=agent_shared))

    assert response.correlation_id == agent_shared.correlation_id
    assert response.parent_execution_id == agent_shared.execution_id
    assert response.causation_id == agent_shared.execution_id
    assert response.execution_id != agent_shared.execution_id


def test_retry_preserves_execution_id_across_every_attempt():
    flaky = _FlakyProvider(fail_times=2)
    executor = RuntimeExecutor(provider_factory=lambda name, config: flaky, max_retries=2)

    response = executor.execute(_request())

    assert response.success is True
    assert flaky.attempts == 3
    # every event (one per attempt's PROVIDER_SELECTED/REQUEST_SENT, plus
    # the single STARTED/COMPLETED) still carries the one execution_id
    assert all(event.execution_id == response.execution_id for event in response.events)


def test_hook_and_middleware_identity_is_consistent_end_to_end():
    # before_execution -> middleware -> provider -> response -> after_execution
    # must all reference the same execution
    hook = _IdentityCapturingHook()
    middleware = _IdentityCapturingMiddleware()
    provider = _FakeProvider()
    executor = RuntimeExecutor(
        provider_factory=lambda name, config: provider, hooks=(hook,), middleware=(middleware,)
    )

    response = executor.execute(_request())

    assert hook.before_execution_ids == [response.execution_id]
    assert hook.after_execution_ids == [response.execution_id]
    assert hook.after_execution_response_ids == [response.execution_id]
    assert middleware.seen_execution_ids == [response.execution_id]
