import dataclasses

import pytest

from app.services.ai.kernel.context import ExecutionContext
from app.services.ai.kernel.execution import ExecutionRequest
from app.services.ai.kernel.hooks import KernelHook
from app.services.ai.kernel.middleware import KernelMiddleware
from app.services.ai.kernel.pipeline import RuntimePipeline


class _FakeMiddleware(KernelMiddleware):
    def before_execute(self, request):
        return request

    def after_execute(self, request, response):
        return response

    def on_error(self, request, error):
        return None


class _FakeHook(KernelHook):
    def before_execution(self, request):
        return None

    def after_execution(self, request, response):
        return None

    def execution_failed(self, request, error):
        return None


def test_pipeline_defaults_to_no_middleware_or_hooks():
    pipeline = RuntimePipeline()

    assert pipeline.middleware == ()
    assert pipeline.hooks == ()


def test_pipeline_construction_with_middleware_and_hooks():
    middleware = (_FakeMiddleware(),)
    hooks = (_FakeHook(),)

    pipeline = RuntimePipeline(middleware=middleware, hooks=hooks)

    assert pipeline.middleware == middleware
    assert pipeline.hooks == hooks


def test_pipeline_is_frozen():
    pipeline = RuntimePipeline()

    with pytest.raises(dataclasses.FrozenInstanceError):
        pipeline.middleware = (_FakeMiddleware(),)


def test_pipeline_middleware_and_hooks_are_tuples():
    pipeline = RuntimePipeline(middleware=(_FakeMiddleware(),), hooks=(_FakeHook(),))

    assert isinstance(pipeline.middleware, tuple)
    assert isinstance(pipeline.hooks, tuple)


def test_pipeline_run_raises_not_implemented_error():
    pipeline = RuntimePipeline()
    request = ExecutionRequest(capability="conversation", payload=None, context=ExecutionContext())

    with pytest.raises(NotImplementedError):
        pipeline.run(request)
