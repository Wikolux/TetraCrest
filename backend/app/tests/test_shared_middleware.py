import pytest

from app.services.ai.shared.middleware import GenericMiddleware, GenericMiddlewarePipeline


class _RecordingMiddleware(GenericMiddleware):
    def __init__(self, name, log):
        self.name = name
        self.log = log

    def __call__(self, context, subject, call_next):
        self.log.append(f"{self.name}-before")
        result = call_next(context, subject)
        self.log.append(f"{self.name}-after")
        return result


def test_generic_middleware_is_abstract():
    with pytest.raises(TypeError):
        GenericMiddleware()


def test_empty_pipeline_calls_the_handler_directly():
    pipeline = GenericMiddlewarePipeline()

    result = pipeline.run(None, None, lambda c, s: "result")

    assert result == "result"


def test_single_middleware_wraps_the_handler():
    log = []
    pipeline = GenericMiddlewarePipeline(middleware=(_RecordingMiddleware("m1", log),))

    pipeline.run(None, None, lambda c, s: "result")

    assert log == ["m1-before", "m1-after"]


def test_middleware_runs_in_onion_order():
    log = []
    pipeline = GenericMiddlewarePipeline(middleware=(_RecordingMiddleware("m1", log), _RecordingMiddleware("m2", log)))

    pipeline.run(None, None, lambda c, s: "result")

    assert log == ["m1-before", "m2-before", "m2-after", "m1-after"]


def test_middleware_can_short_circuit_without_calling_call_next():
    handler_called = []

    class _ShortCircuit(GenericMiddleware):
        def __call__(self, context, subject, call_next):
            return "short-circuited"

    pipeline = GenericMiddlewarePipeline(middleware=(_ShortCircuit(),))

    result = pipeline.run(None, None, lambda c, s: handler_called.append(True))

    assert result == "short-circuited"
    assert handler_called == []
