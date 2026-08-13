"""VisionExecutor - owns the full execution lifecycle for one
VisionRequest: provider resolution (via the capability-appropriate
*ProviderFactory only - never a specific vendor), the middleware chain,
timeout wrapping, retry orchestration, event emission, and hook
execution. Mirrors RuntimeExecutor almost exactly, composing the same
Kernel/Runtime interfaces (RuntimeTimeout, RetryPolicy via max_retries,
CancellationToken, ExecutionMetrics, SharedExecutionContext) rather than
duplicating any of them.

Always returns a VisionResponse; a provider/timeout/cancellation failure
is reported there via success=False/error, never raised.
"""

import dataclasses
import time

from app.services.ai.kernel.metrics import ExecutionMetrics
from app.services.ai.runtime.timeout import RuntimeTimeout, RuntimeTimeoutError
from app.services.ai.shared.exceptions import AIProviderError
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.shared.provider_config import BaseProviderConfig
from app.services.ai.vision.analysis.provider_factory import AnalysisProviderFactory
from app.services.ai.vision.context import VisionContext
from app.services.ai.vision.document.provider_factory import DocumentVisionProviderFactory
from app.services.ai.vision.events import VisionEvent, VisionEventPublisher, VisionEventType
from app.services.ai.vision.extraction.provider_factory import ExtractionProviderFactory
from app.services.ai.vision.capabilities.enums import VisionCapabilityCategory
from app.services.ai.vision.hooks import VisionHook
from app.services.ai.vision.image.provider_factory import ImageVisionProviderFactory
from app.services.ai.vision.middleware import VisionMiddleware, VisionMiddlewarePipeline
from app.services.ai.vision.request import VisionRequest
from app.services.ai.vision.response import VisionResponse
from app.services.ai.vision.shared.exceptions import VisionExecutionError

_MS_PER_SECOND = 1000

# Keyed by VisionCapabilityCategory (not a raw string) - capability is the
# dispatch language here, exactly like AgentCapability drives the
# Executive's Dispatcher and ToolCapability drives ToolDiscovery. Since
# VisionCapabilityCategory is a StrEnum, a caller that still passes the
# literal string ("image") continues to match these tables identically -
# this is a type-safety improvement, not a behavior change.
_CAPABILITY_METHOD: dict[VisionCapabilityCategory, str] = {
    VisionCapabilityCategory.IMAGE: "describe",
    VisionCapabilityCategory.DOCUMENT: "understand",
    VisionCapabilityCategory.EXTRACTION: "extract",
    VisionCapabilityCategory.ANALYSIS: "analyze",
}

_CAPABILITY_FACTORY = {
    VisionCapabilityCategory.IMAGE: ImageVisionProviderFactory.create,
    VisionCapabilityCategory.DOCUMENT: DocumentVisionProviderFactory.create,
    VisionCapabilityCategory.EXTRACTION: ExtractionProviderFactory.create,
    VisionCapabilityCategory.ANALYSIS: AnalysisProviderFactory.create,
}

_CAPABILITY_EVENT: dict[VisionCapabilityCategory, VisionEventType] = {
    VisionCapabilityCategory.IMAGE: VisionEventType.IMAGE_ANALYZED,
    VisionCapabilityCategory.DOCUMENT: VisionEventType.DOCUMENT_ANALYZED,
}


class VisionExecutor:
    def __init__(
        self,
        middleware: tuple[VisionMiddleware, ...] = (),
        hooks: tuple[VisionHook, ...] = (),
        event_publisher: VisionEventPublisher | None = None,
        max_retries: int = 0,
        provider_factory_map: dict | None = None,
    ) -> None:
        self.middleware_pipeline = VisionMiddlewarePipeline(middleware=middleware)
        self.hooks = hooks
        self.event_publisher = event_publisher or VisionEventPublisher()
        self.max_retries = max_retries
        self.provider_factory_map = provider_factory_map or _CAPABILITY_FACTORY

    def execute(self, request: VisionRequest) -> VisionResponse:
        if request.capability_category not in _CAPABILITY_METHOD:
            return VisionResponse(success=False, error=f"Unknown capability_category: {request.capability_category!r}")

        shared = request.parent_shared.child() if request.parent_shared is not None else SharedExecutionContext()
        context = VisionContext(shared=shared, capability_category=request.capability_category)
        events: list[VisionEvent] = []
        start = time.monotonic()

        self._emit(events, context, VisionEventType.VISION_STARTED)
        self._call_hooks("before_analysis", context, request)

        if self._is_cancelled(request):
            return self._finish_cancelled(context, events, start)

        result: VisionResponse | None = None
        provider_error: str | None = None
        attempt = 0

        for attempt in range(1, self.max_retries + 2):
            if self._is_cancelled(request):
                return self._finish_cancelled(context, events, start)
            try:
                result = self._attempt(context, request, events)
            except AIProviderError as exc:
                provider_error = str(exc)
                break
            if result.success:
                break

        if provider_error is not None:
            result = VisionResponse(success=False, error=provider_error)

        return self._finish(context, events, start, result, attempt - 1)

    def _attempt(self, context: VisionContext, request: VisionRequest, events: list[VisionEvent]) -> VisionResponse:
        def _handler(ctx, req):
            provider_factory = self.provider_factory_map[req.capability_category]
            provider = provider_factory(req.provider, BaseProviderConfig())
            method = getattr(provider, _CAPABILITY_METHOD[req.capability_category])
            raw = RuntimeTimeout(None).run(method, req)
            if not isinstance(raw, VisionResponse):
                raise VisionExecutionError(
                    f"{req.capability_category} provider must return a VisionResponse, got {type(raw).__name__}"
                )
            return raw

        try:
            response = self.middleware_pipeline.run(context, request, _handler)
        except RuntimeTimeoutError as exc:
            self._emit(events, context, VisionEventType.VISION_FAILED, error=str(exc))
            self._call_hooks("on_timeout", context)
            return VisionResponse(success=False, error=str(exc))
        except AIProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - a provider failure must never escape as a raw exception
            self._call_hooks("on_failure", context, exc)
            return VisionResponse(success=False, error=str(exc))

        self._emit_content_events(events, context, request, response)
        return response

    def _emit_content_events(
        self, events: list[VisionEvent], context: VisionContext, request: VisionRequest, response: VisionResponse
    ) -> None:
        capability_event = _CAPABILITY_EVENT.get(request.capability_category)
        if capability_event is not None:
            self._emit(events, context, capability_event)
        if response.extracted_text:
            self._emit(events, context, VisionEventType.TEXT_EXTRACTED)
        if response.tables:
            self._emit(events, context, VisionEventType.TABLE_EXTRACTED)
        if response.objects:
            self._emit(events, context, VisionEventType.OBJECTS_DETECTED)

    def _finish(
        self,
        context: VisionContext,
        events: list[VisionEvent],
        start: float,
        result: VisionResponse | None,
        retry_count: int,
    ) -> VisionResponse:
        duration_ms = (time.monotonic() - start) * _MS_PER_SECOND
        metrics = ExecutionMetrics(duration_ms=duration_ms, retry_count=max(retry_count, 0), execution_id=context.execution_id)

        if result is not None and result.success:
            self._emit(events, context, VisionEventType.VISION_COMPLETED)
        else:
            self._emit(events, context, VisionEventType.VISION_FAILED, error=result.error if result else "Unknown error")

        final = dataclasses.replace(
            result if result is not None else VisionResponse(success=False, error="Unknown error"),
            duration_ms=duration_ms,
            metrics=metrics,
            **context.shared.identity_fields(),
        )
        self._call_hooks("after_analysis", context, final)
        return final

    def _finish_cancelled(self, context: VisionContext, events: list[VisionEvent], start: float) -> VisionResponse:
        self._emit(events, context, VisionEventType.VISION_FAILED, error="Execution was cancelled")
        self._call_hooks("on_cancel", context)
        duration_ms = (time.monotonic() - start) * _MS_PER_SECOND
        metrics = ExecutionMetrics(duration_ms=duration_ms, retry_count=0, execution_id=context.execution_id)
        response = VisionResponse(
            success=False,
            error="Execution was cancelled",
            duration_ms=duration_ms,
            metrics=metrics,
            **context.shared.identity_fields(),
        )
        self._call_hooks("after_analysis", context, response)
        return response

    @staticmethod
    def _is_cancelled(request: VisionRequest) -> bool:
        return request.cancellation_token is not None and request.cancellation_token.cancelled()

    def _emit(self, events: list[VisionEvent], context: VisionContext, event_type: VisionEventType, **data) -> None:
        event = VisionEvent(
            event_type=event_type,
            execution_id=context.execution_id,
            correlation_id=context.correlation_id,
            data=data,
        )
        events.append(event)
        self.event_publisher.publish(event)

    def _call_hooks(self, method_name: str, *args) -> None:
        for hook in self.hooks:
            getattr(hook, method_name)(*args)
