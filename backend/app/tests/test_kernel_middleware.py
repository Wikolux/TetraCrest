import pytest

from app.services.ai.kernel.context import ExecutionContext
from app.services.ai.kernel.execution import ExecutionRequest, ExecutionResponse
from app.services.ai.kernel.middleware import KernelMiddleware


class _CompleteMiddleware(KernelMiddleware):
    def before_execute(self, request):
        return request

    def after_execute(self, request, response):
        return response

    def on_error(self, request, error):
        return None


def test_kernel_middleware_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        KernelMiddleware()


def test_conforming_subclass_can_be_instantiated():
    middleware = _CompleteMiddleware()

    assert isinstance(middleware, KernelMiddleware)


def test_before_execute_can_return_a_request():
    middleware = _CompleteMiddleware()
    request = ExecutionRequest(capability="conversation", payload=None, context=ExecutionContext())

    assert middleware.before_execute(request) is request


def test_after_execute_can_return_a_response():
    middleware = _CompleteMiddleware()
    request = ExecutionRequest(capability="conversation", payload=None, context=ExecutionContext())
    response = ExecutionResponse(success=True)

    assert middleware.after_execute(request, response) is response


def test_on_error_is_callable():
    middleware = _CompleteMiddleware()
    request = ExecutionRequest(capability="conversation", payload=None, context=ExecutionContext())

    assert middleware.on_error(request, RuntimeError("boom")) is None


@pytest.mark.parametrize("missing_member", ["before_execute", "after_execute", "on_error"])
def test_subclass_missing_any_required_member_cannot_be_instantiated(missing_member):
    members = {
        "before_execute": lambda self, request: request,
        "after_execute": lambda self, request, response: response,
        "on_error": lambda self, request, error: None,
    }
    del members[missing_member]

    IncompleteMiddleware = type("IncompleteMiddleware", (KernelMiddleware,), members)

    with pytest.raises(TypeError):
        IncompleteMiddleware()
