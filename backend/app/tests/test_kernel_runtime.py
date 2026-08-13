import pytest

from app.services.ai.kernel.context import ExecutionContext
from app.services.ai.kernel.execution import ExecutionRequest
from app.services.ai.kernel.pipeline import RuntimePipeline
from app.services.ai.kernel.registry import RuntimeRegistry
from app.services.ai.kernel.runtime import KernelRuntime


def _request(capability="conversation", payload=None, context=None):
    return ExecutionRequest(capability=capability, payload=payload, context=context or ExecutionContext())


# --- construction / dependency injection --------------------------------------


def test_default_construction_builds_a_registry_and_pipeline():
    runtime = KernelRuntime()

    assert isinstance(runtime.registry, RuntimeRegistry)
    assert isinstance(runtime.pipeline, RuntimePipeline)


def test_injected_registry_is_used():
    registry = RuntimeRegistry()

    runtime = KernelRuntime(registry=registry)

    assert runtime.registry is registry


def test_injected_pipeline_is_used():
    pipeline = RuntimePipeline()

    runtime = KernelRuntime(pipeline=pipeline)

    assert runtime.pipeline is pipeline


def test_default_pipeline_is_built_from_the_injected_registry():
    from app.services.ai.kernel.middleware import KernelMiddleware

    class _FakeMiddleware(KernelMiddleware):
        def before_execute(self, request):
            return request

        def after_execute(self, request, response):
            return response

        def on_error(self, request, error):
            return None

    registry = RuntimeRegistry()
    middleware = _FakeMiddleware()
    registry.register_middleware(middleware)

    runtime = KernelRuntime(registry=registry)

    assert runtime.pipeline.middleware == (middleware,)


def test_two_runtimes_constructed_with_default_registries_do_not_share_state():
    first = KernelRuntime()
    second = KernelRuntime()

    assert first.registry is not second.registry


# --- execution validation ------------------------------------------------------


def test_execute_rejects_non_execution_request():
    runtime = KernelRuntime()

    with pytest.raises(TypeError):
        runtime.execute("not a request")


def test_execute_rejects_request_with_empty_capability():
    runtime = KernelRuntime()
    request = _request(capability="")

    with pytest.raises(ValueError):
        runtime.execute(request)


def test_execute_rejects_request_with_none_capability():
    # capability is a required constructor field on ExecutionRequest, but
    # nothing stops someone constructing one with capability=None via
    # dataclasses.replace or similar - execute() must still reject it
    import dataclasses

    request = _request(capability="conversation")
    request_with_none_capability = dataclasses.replace(request, capability=None)
    runtime = KernelRuntime()

    with pytest.raises(ValueError):
        runtime.execute(request_with_none_capability)


def test_execute_rejects_request_with_invalid_context_type():
    # ExecutionRequest is frozen, so this bypasses normal construction the
    # way a caller assembling a request dynamically and incorrectly might -
    # execute() must still catch it rather than fail deep inside the kernel
    request = _request()
    object.__setattr__(request, "context", "not a context")
    runtime = KernelRuntime()

    with pytest.raises(TypeError):
        runtime.execute(request)


# --- generic payload support -----------------------------------------------------


@pytest.mark.parametrize("payload", [{"query": "hi"}, "raw text", [1, 2, 3], object(), None, 42])
def test_execute_validation_accepts_any_payload_shape(payload):
    runtime = KernelRuntime()
    request = _request(payload=payload)

    # validation must never reject based on payload shape - the kernel
    # doesn't know or care what's inside it. It should get past
    # validation and hit the "architecture only" NotImplementedError.
    with pytest.raises(NotImplementedError):
        runtime.execute(request)


# --- unknown / arbitrary capability behavior --------------------------------------


@pytest.mark.parametrize("capability", ["conversation", "vision", "totally-made-up-capability"])
def test_execute_raises_not_implemented_for_any_syntactically_valid_capability(capability):
    # with no resolution logic implemented yet, a "known" capability like
    # "conversation" and a nonsense one behave identically - both are
    # architecture-only and raise NotImplementedError, never a crash or a
    # silent success
    runtime = KernelRuntime()
    request = _request(capability=capability)

    with pytest.raises(NotImplementedError):
        runtime.execute(request)


# --- well-formed request still architecture-only --------------------------------


def test_execute_raises_not_implemented_error_for_a_well_formed_request():
    runtime = KernelRuntime()
    request = _request()

    with pytest.raises(NotImplementedError, match="architecture only"):
        runtime.execute(request)


def test_execute_does_not_mutate_the_request():
    # copy.deepcopy can't be used here - a frozen dataclass holding a
    # MappingProxyType isn't picklable/deepcopy-able by default. Compare
    # the mutable payload directly instead: it's the one part of the
    # request that could be mutated in place without violating dataclass
    # immutability.
    runtime = KernelRuntime()
    payload = {"query": "hi"}
    request = _request(payload=payload)
    original_payload = dict(payload)

    with pytest.raises(NotImplementedError):
        runtime.execute(request)

    assert request.payload == original_payload
    assert request.capability == "conversation"
