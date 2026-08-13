import pytest

from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.middleware import MiddlewarePipeline, RuntimeMiddleware
from app.services.ai.runtime.types import RuntimeContext, RuntimeExecutionResult, RuntimeRequest
from app.services.ai.shared.middleware import GenericMiddleware, GenericMiddlewarePipeline
from app.services.prompt_builder.types import PromptPackage


def test_runtime_middleware_is_built_on_the_generic_middleware_not_a_parallel_type():
    assert issubclass(RuntimeMiddleware, GenericMiddleware)


def test_pipeline_is_built_on_the_generic_pipeline_not_a_parallel_type():
    assert issubclass(MiddlewarePipeline, GenericMiddlewarePipeline)


def _request():
    return RuntimeRequest(
        organization_id=1, prompt_package=PromptPackage(system_prompt="s"), provider=ProviderName.OPENAI
    )


def _handler(context, request):
    return RuntimeExecutionResult(success=True)


class _RecordingMiddleware(RuntimeMiddleware):
    def __init__(self, name, log):
        self.name = name
        self.log = log

    def __call__(self, context, request, call_next):
        self.log.append(f"{self.name}-before")
        result = call_next(context, request)
        self.log.append(f"{self.name}-after")
        return result


class _ShortCircuitMiddleware(RuntimeMiddleware):
    def __call__(self, context, request, call_next):
        return RuntimeExecutionResult(success=False, error="short-circuited")


def test_runtime_middleware_is_abstract():
    with pytest.raises(TypeError):
        RuntimeMiddleware()


def test_empty_pipeline_calls_the_handler_directly():
    pipeline = MiddlewarePipeline()

    result = pipeline.run(RuntimeContext(), _request(), _handler)

    assert result.success is True


def test_single_middleware_wraps_the_handler():
    log = []
    pipeline = MiddlewarePipeline(middleware=(_RecordingMiddleware("m1", log),))

    pipeline.run(RuntimeContext(), _request(), _handler)

    assert log == ["m1-before", "m1-after"]


def test_middleware_runs_in_onion_order():
    log = []
    pipeline = MiddlewarePipeline(
        middleware=(_RecordingMiddleware("m1", log), _RecordingMiddleware("m2", log))
    )

    pipeline.run(RuntimeContext(), _request(), _handler)

    # first middleware is outermost: first to run before, last to run after
    assert log == ["m1-before", "m2-before", "m2-after", "m1-after"]


def test_middleware_can_short_circuit_without_calling_call_next():
    handler_called = []
    pipeline = MiddlewarePipeline(middleware=(_ShortCircuitMiddleware(),))

    result = pipeline.run(RuntimeContext(), _request(), lambda c, r: handler_called.append(True))

    assert result.success is False
    assert result.error == "short-circuited"
    assert handler_called == []


def test_middleware_can_inspect_the_handlers_result():
    seen = []

    class _InspectingMiddleware(RuntimeMiddleware):
        def __call__(self, context, request, call_next):
            result = call_next(context, request)
            seen.append(result.success)
            return result

    pipeline = MiddlewarePipeline(middleware=(_InspectingMiddleware(),))

    pipeline.run(RuntimeContext(), _request(), _handler)

    assert seen == [True]
