import pytest

from app.services.ai.kernel.context import ExecutionContext
from app.services.ai.kernel.execution import ExecutionRequest, ExecutionResponse
from app.services.ai.kernel.hooks import KernelHook


class _CompleteHook(KernelHook):
    def __init__(self):
        self.calls = []

    def before_execution(self, request):
        self.calls.append(("before_execution", request))

    def after_execution(self, request, response):
        self.calls.append(("after_execution", request, response))

    def execution_failed(self, request, error):
        self.calls.append(("execution_failed", request, error))


def test_kernel_hook_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        KernelHook()


def test_conforming_subclass_can_be_instantiated():
    hook = _CompleteHook()

    assert isinstance(hook, KernelHook)


def test_before_execution_returns_none():
    hook = _CompleteHook()
    request = ExecutionRequest(capability="conversation", payload=None, context=ExecutionContext())

    assert hook.before_execution(request) is None


def test_after_execution_returns_none():
    hook = _CompleteHook()
    request = ExecutionRequest(capability="conversation", payload=None, context=ExecutionContext())
    response = ExecutionResponse(success=True)

    assert hook.after_execution(request, response) is None


def test_execution_failed_returns_none():
    hook = _CompleteHook()
    request = ExecutionRequest(capability="conversation", payload=None, context=ExecutionContext())

    assert hook.execution_failed(request, RuntimeError("boom")) is None


def test_hook_observes_without_transforming():
    hook = _CompleteHook()
    request = ExecutionRequest(capability="conversation", payload=None, context=ExecutionContext())
    response = ExecutionResponse(success=True)

    hook.before_execution(request)
    hook.after_execution(request, response)

    assert hook.calls == [("before_execution", request), ("after_execution", request, response)]


@pytest.mark.parametrize("missing_member", ["before_execution", "after_execution", "execution_failed"])
def test_subclass_missing_any_required_member_cannot_be_instantiated(missing_member):
    members = {
        "before_execution": lambda self, request: None,
        "after_execution": lambda self, request, response: None,
        "execution_failed": lambda self, request, error: None,
    }
    del members[missing_member]

    IncompleteHook = type("IncompleteHook", (KernelHook,), members)

    with pytest.raises(TypeError):
        IncompleteHook()
