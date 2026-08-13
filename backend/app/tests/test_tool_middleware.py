import pytest

from app.services.ai.shared.middleware import GenericMiddleware, GenericMiddlewarePipeline
from app.services.ai.tools.middleware import ToolMiddleware, ToolMiddlewarePipeline
from app.services.ai.tools.result import ToolResult


def test_tool_middleware_is_built_on_the_generic_middleware_not_a_parallel_type():
    assert issubclass(ToolMiddleware, GenericMiddleware)


def test_pipeline_is_built_on_the_generic_pipeline_not_a_parallel_type():
    assert issubclass(ToolMiddlewarePipeline, GenericMiddlewarePipeline)


def _handler(context, tool):
    return ToolResult(success=True)


class _RecordingMiddleware(ToolMiddleware):
    def __init__(self, name, log):
        self.name = name
        self.log = log

    def __call__(self, context, tool, call_next):
        self.log.append(f"{self.name}-before")
        result = call_next(context, tool)
        self.log.append(f"{self.name}-after")
        return result


class _ShortCircuitMiddleware(ToolMiddleware):
    def __call__(self, context, tool, call_next):
        return ToolResult(success=False, error="short-circuited")


def test_tool_middleware_is_abstract():
    with pytest.raises(TypeError):
        ToolMiddleware()


def test_empty_pipeline_calls_the_handler_directly():
    pipeline = ToolMiddlewarePipeline()

    result = pipeline.run(None, None, _handler)

    assert result.success is True


def test_single_middleware_wraps_the_handler():
    log = []
    pipeline = ToolMiddlewarePipeline(middleware=(_RecordingMiddleware("m1", log),))

    pipeline.run(None, None, _handler)

    assert log == ["m1-before", "m1-after"]


def test_middleware_runs_in_onion_order():
    log = []
    pipeline = ToolMiddlewarePipeline(middleware=(_RecordingMiddleware("m1", log), _RecordingMiddleware("m2", log)))

    pipeline.run(None, None, _handler)

    assert log == ["m1-before", "m2-before", "m2-after", "m1-after"]


def test_middleware_can_short_circuit_without_calling_call_next():
    handler_called = []
    pipeline = ToolMiddlewarePipeline(middleware=(_ShortCircuitMiddleware(),))

    result = pipeline.run(None, None, lambda c, t: handler_called.append(True))

    assert result.success is False
    assert result.error == "short-circuited"
    assert handler_called == []


def test_middleware_can_inspect_the_handlers_result():
    seen = []

    class _InspectingMiddleware(ToolMiddleware):
        def __call__(self, context, tool, call_next):
            result = call_next(context, tool)
            seen.append(result.success)
            return result

    pipeline = ToolMiddlewarePipeline(middleware=(_InspectingMiddleware(),))

    pipeline.run(None, None, _handler)

    assert seen == [True]
