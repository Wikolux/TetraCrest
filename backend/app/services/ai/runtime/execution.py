"""RuntimeExecutor - owns the full execution lifecycle for one
RuntimeRequest.

Responsibilities: provider invocation (via ConversationProviderFactory
only - never a specific vendor), the middleware chain, timeout wrapping,
retry orchestration, event emission, and hook execution. Always returns a
RuntimeResponse; a provider/timeout/cancellation failure is reported
there via success=False/error, never raised, matching how every other
execution engine in this platform behaves. AIRuntime delegates every
execute() call to this class.
"""

import dataclasses
import time
from typing import Callable

from app.services.ai.conversation.provider_factory import ConversationProviderFactory
from app.services.ai.runtime.events import RuntimeEventPublisher
from app.services.ai.runtime.hooks import RuntimeHook
from app.services.ai.runtime.middleware import MiddlewarePipeline, RuntimeMiddleware
from app.services.ai.runtime.timeout import RuntimeTimeout, RuntimeTimeoutError
from app.services.ai.runtime.types import (
    EventType,
    RuntimeContext,
    RuntimeEvent,
    RuntimeExecutionResult,
    RuntimeRequest,
    RuntimeResponse,
)
from app.services.ai.shared.exceptions import AIProviderError
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.shared.provider_config import ConversationProviderConfig

_MS_PER_SECOND = 1000

ProviderFactoryCallable = Callable[..., object]


class RuntimeExecutor:
    """Executes one RuntimeRequest through the middleware chain against a
    provider resolved via ConversationProviderFactory, with retry,
    timeout, event, and hook support.

    Constructed once, called many times: execute() keeps every per-call
    value (RuntimeContext, the events list) local to that call rather than
    on self, so concurrent or sequential calls never interfere with each
    other.
    """

    def __init__(
        self,
        middleware: tuple[RuntimeMiddleware, ...] = (),
        hooks: tuple[RuntimeHook, ...] = (),
        event_publisher: RuntimeEventPublisher | None = None,
        max_retries: int = 0,
        provider_factory: ProviderFactoryCallable = ConversationProviderFactory.create,
    ) -> None:
        self.middleware_pipeline = MiddlewarePipeline(middleware=middleware)
        self.hooks = hooks
        self.event_publisher = event_publisher or RuntimeEventPublisher()
        self.max_retries = max_retries
        self.provider_factory = provider_factory

    def execute(self, request: RuntimeRequest) -> RuntimeResponse:
        shared = request.parent_shared.child() if request.parent_shared is not None else SharedExecutionContext()
        context = RuntimeContext(
            shared=shared, provider=request.provider, provider_model=request.model, timeout=request.timeout
        )
        events: list[RuntimeEvent] = []
        start = time.monotonic()

        self._emit(events, context, EventType.STARTED)
        self._call_hooks("before_execution", context, request)

        if self._is_cancelled(request):
            return self._finish_cancelled(request, context, events, start)

        result: RuntimeExecutionResult | None = None
        for attempt_number in range(1, self.max_retries + 2):
            context = dataclasses.replace(context, attempt=attempt_number, retry_count=attempt_number - 1)

            if self._is_cancelled(request):
                return self._finish_cancelled(request, context, events, start)

            result = self._attempt(context, request, events)
            if result.success or not result.retryable:
                break

        return self._finish(request, context, events, start, result)

    def _attempt(
        self, context: RuntimeContext, request: RuntimeRequest, events: list[RuntimeEvent]
    ) -> RuntimeExecutionResult:
        attempt_start = time.monotonic()

        def _handler(ctx: RuntimeContext, req: RuntimeRequest) -> RuntimeExecutionResult:
            provider = self.provider_factory(req.provider, self._build_config(req))
            self._emit(events, ctx, EventType.PROVIDER_SELECTED, provider=str(req.provider))
            self._emit(events, ctx, EventType.REQUEST_SENT)
            conversation_response = RuntimeTimeout(req.timeout).run(provider.generate, req.prompt_package)
            self._emit(events, ctx, EventType.RESPONSE_RECEIVED)
            return RuntimeExecutionResult(
                success=True,
                conversation_response=conversation_response,
                attempt=ctx.attempt,
                duration_ms=(time.monotonic() - attempt_start) * _MS_PER_SECOND,
            )

        try:
            return self.middleware_pipeline.run(context, request, _handler)
        except AIProviderError as exc:
            return RuntimeExecutionResult(
                success=False,
                error=str(exc),
                attempt=context.attempt,
                duration_ms=(time.monotonic() - attempt_start) * _MS_PER_SECOND,
                retryable=False,
            )
        except RuntimeTimeoutError as exc:
            self._emit(events, context, EventType.TIMEOUT)
            self._call_hooks("on_timeout", context)
            return RuntimeExecutionResult(
                success=False,
                error=str(exc),
                attempt=context.attempt,
                duration_ms=(time.monotonic() - attempt_start) * _MS_PER_SECOND,
            )
        except Exception as exc:  # noqa: BLE001 - a provider failure must never escape as a raw exception
            self._call_hooks("on_error", context, exc)
            return RuntimeExecutionResult(
                success=False,
                error=str(exc),
                attempt=context.attempt,
                duration_ms=(time.monotonic() - attempt_start) * _MS_PER_SECOND,
            )

    def _finish(
        self,
        request: RuntimeRequest,
        context: RuntimeContext,
        events: list[RuntimeEvent],
        start: float,
        result: RuntimeExecutionResult | None,
    ) -> RuntimeResponse:
        latency_ms = (time.monotonic() - start) * _MS_PER_SECOND

        if result is not None and result.success:
            self._emit(events, context, EventType.COMPLETED)
            response = RuntimeResponse(
                success=True,
                provider=request.provider,
                conversation_response=result.conversation_response,
                latency_ms=latency_ms,
                usage=result.conversation_response.usage if result.conversation_response else None,
                events=tuple(events),
                **context.shared.identity_fields(),
            )
        else:
            self._emit(events, context, EventType.FAILED)
            response = RuntimeResponse(
                success=False,
                provider=request.provider,
                latency_ms=latency_ms,
                error=result.error if result is not None else "Unknown error",
                events=tuple(events),
                **context.shared.identity_fields(),
            )

        self._call_hooks("after_execution", context, response)
        return response

    def _finish_cancelled(
        self,
        request: RuntimeRequest,
        context: RuntimeContext,
        events: list[RuntimeEvent],
        start: float,
    ) -> RuntimeResponse:
        self._emit(events, context, EventType.CANCELLED)
        self._call_hooks("on_cancel", context)
        response = RuntimeResponse(
            success=False,
            provider=request.provider,
            latency_ms=(time.monotonic() - start) * _MS_PER_SECOND,
            error="Execution was cancelled",
            events=tuple(events),
            **context.shared.identity_fields(),
        )
        self._call_hooks("after_execution", context, response)
        return response

    @staticmethod
    def _is_cancelled(request: RuntimeRequest) -> bool:
        return request.cancellation_token is not None and request.cancellation_token.cancelled()

    @staticmethod
    def _build_config(request: RuntimeRequest) -> ConversationProviderConfig:
        return ConversationProviderConfig(
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

    def _emit(self, events: list[RuntimeEvent], context: RuntimeContext, event_type: EventType, **data) -> None:
        event = RuntimeEvent(
            event_type=event_type,
            execution_id=context.execution_id,
            data=data,
        )
        events.append(event)
        self.event_publisher.publish(event)

    def _call_hooks(self, method_name: str, *args) -> None:
        for hook in self.hooks:
            getattr(hook, method_name)(*args)
