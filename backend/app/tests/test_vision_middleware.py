import pytest

from app.services.ai.shared.middleware import GenericMiddleware, GenericMiddlewarePipeline
from app.services.ai.vision.middleware import VisionMiddleware, VisionMiddlewarePipeline


def _handler(context, provider):
    return "result"


class _RecordingMiddleware(VisionMiddleware):
    def __init__(self, name, log):
        self.name = name
        self.log = log

    def __call__(self, context, provider, call_next):
        self.log.append(f"{self.name}-before")
        result = call_next(context, provider)
        self.log.append(f"{self.name}-after")
        return result


def test_vision_middleware_is_built_on_the_generic_middleware():
    assert issubclass(VisionMiddleware, GenericMiddleware)


def test_vision_middleware_is_abstract():
    with pytest.raises(TypeError):
        VisionMiddleware()


def test_vision_middleware_pipeline_is_built_on_the_generic_pipeline():
    assert issubclass(VisionMiddlewarePipeline, GenericMiddlewarePipeline)


def test_empty_pipeline_calls_the_handler_directly():
    pipeline = VisionMiddlewarePipeline()

    result = pipeline.run(None, None, _handler)

    assert result == "result"


def test_middleware_runs_in_onion_order():
    log = []
    pipeline = VisionMiddlewarePipeline(middleware=(_RecordingMiddleware("m1", log), _RecordingMiddleware("m2", log)))

    pipeline.run(None, None, _handler)

    assert log == ["m1-before", "m2-before", "m2-after", "m1-after"]


def test_middleware_can_short_circuit_and_skip_the_handler():
    handler_called = []

    class _Blocking(VisionMiddleware):
        def __call__(self, context, provider, call_next):
            return "blocked"

    pipeline = VisionMiddlewarePipeline(middleware=(_Blocking(),))

    result = pipeline.run(None, None, lambda c, p: handler_called.append(True))

    assert result == "blocked"
    assert handler_called == []
