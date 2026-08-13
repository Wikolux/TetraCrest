import pytest

from app.services.ai.kernel.capability_runtime import CapabilityRuntime
from app.services.ai.kernel.context import ExecutionContext
from app.services.ai.kernel.execution import ExecutionRequest, ExecutionResponse


class _CompleteRuntime(CapabilityRuntime):
    def validate(self, request):
        return None

    def prepare(self, request):
        return request

    def execute(self, request):
        return ExecutionResponse(success=True, payload="ok")

    def cleanup(self, request):
        return None

    def health_check(self) -> bool:
        return True


def _request():
    return ExecutionRequest(capability="conversation", payload=None, context=ExecutionContext())


def test_capability_runtime_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        CapabilityRuntime()


def test_conforming_subclass_can_be_instantiated():
    runtime = _CompleteRuntime()

    assert isinstance(runtime, CapabilityRuntime)


def test_validate_is_callable():
    assert _CompleteRuntime().validate(_request()) is None


def test_prepare_returns_a_request():
    runtime = _CompleteRuntime()
    request = _request()

    assert runtime.prepare(request) is request


def test_execute_returns_an_execution_response():
    response = _CompleteRuntime().execute(_request())

    assert isinstance(response, ExecutionResponse)
    assert response.payload == "ok"


def test_cleanup_is_callable():
    assert _CompleteRuntime().cleanup(_request()) is None


def test_health_check_is_callable():
    assert _CompleteRuntime().health_check() is True


@pytest.mark.parametrize(
    "missing_member", ["validate", "prepare", "execute", "cleanup", "health_check"]
)
def test_subclass_missing_any_required_member_cannot_be_instantiated(missing_member):
    members = {
        "validate": lambda self, request: None,
        "prepare": lambda self, request: request,
        "execute": lambda self, request: ExecutionResponse(success=True),
        "cleanup": lambda self, request: None,
        "health_check": lambda self: True,
    }
    del members[missing_member]

    IncompleteRuntime = type("IncompleteRuntime", (CapabilityRuntime,), members)

    with pytest.raises(TypeError):
        IncompleteRuntime()
