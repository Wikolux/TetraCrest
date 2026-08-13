import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.kernel.context import ExecutionContext
from app.services.ai.kernel.execution import ExecutionRequest, ExecutionResponse
from app.services.ai.kernel.state import ExecutionState


def _context():
    return ExecutionContext(capability="conversation")


# --- ExecutionRequest --------------------------------------------------------


def test_execution_request_construction():
    context = _context()

    request = ExecutionRequest(capability="conversation", payload={"query": "hi"}, context=context)

    assert request.capability == "conversation"
    assert request.payload == {"query": "hi"}
    assert request.context is context


def test_execution_request_options_defaults_to_empty_read_only_mapping():
    request = ExecutionRequest(capability="conversation", payload=None, context=_context())

    assert isinstance(request.options, MappingProxyType)
    assert dict(request.options) == {}


def test_execution_request_options_coerced_to_read_only():
    request = ExecutionRequest(
        capability="conversation", payload=None, context=_context(), options={"temperature": 0.7}
    )

    assert isinstance(request.options, MappingProxyType)
    assert request.options["temperature"] == 0.7


def test_execution_request_options_cannot_be_mutated():
    request = ExecutionRequest(
        capability="conversation", payload=None, context=_context(), options={"temperature": 0.7}
    )

    with pytest.raises(TypeError):
        request.options["temperature"] = 1.0


def test_execution_request_payload_supports_arbitrary_generic_shapes():
    # the kernel must never assume a specific payload shape - a dict, a
    # string, a list, a custom object, or None must all be accepted
    for payload in ({"a": 1}, "raw text", [1, 2, 3], object(), None):
        request = ExecutionRequest(capability="conversation", payload=payload, context=_context())
        assert request.payload is payload or request.payload == payload


def test_execution_request_is_frozen():
    request = ExecutionRequest(capability="conversation", payload=None, context=_context())

    with pytest.raises(dataclasses.FrozenInstanceError):
        request.capability = "vision"


# --- ExecutionResponse ---------------------------------------------------------


def test_execution_response_construction_minimal():
    response = ExecutionResponse(success=True)

    assert response.success is True
    assert response.payload is None
    assert response.provider is None
    assert response.latency_ms is None
    assert response.usage is None
    assert response.error is None


def test_execution_response_construction_with_all_fields():
    response = ExecutionResponse(
        success=True,
        payload="the answer",
        provider="openai",
        latency_ms=123.4,
        usage={"prompt_tokens": 10, "completion_tokens": 5},
        metadata={"trace": "abc"},
    )

    assert response.payload == "the answer"
    assert response.provider == "openai"
    assert response.latency_ms == 123.4
    assert response.usage == {"prompt_tokens": 10, "completion_tokens": 5}
    assert response.metadata == {"trace": "abc"}


def test_execution_response_failure_case():
    response = ExecutionResponse(success=False, error="provider unavailable")

    assert response.success is False
    assert response.error == "provider unavailable"


def test_execution_response_payload_is_generic():
    for payload in ({"a": 1}, "raw text", [1, 2, 3], object(), None):
        response = ExecutionResponse(success=True, payload=payload)
        assert response.payload is payload or response.payload == payload


def test_execution_response_usage_is_none_by_default_not_an_empty_mapping():
    response = ExecutionResponse(success=True)

    assert response.usage is None


def test_execution_response_usage_coerced_to_read_only_when_provided():
    response = ExecutionResponse(success=True, usage={"total_tokens": 15})

    assert isinstance(response.usage, MappingProxyType)


def test_execution_response_usage_cannot_be_mutated():
    response = ExecutionResponse(success=True, usage={"total_tokens": 15})

    with pytest.raises(TypeError):
        response.usage["total_tokens"] = 999


def test_execution_response_metadata_defaults_to_empty_read_only_mapping():
    response = ExecutionResponse(success=True)

    assert isinstance(response.metadata, MappingProxyType)
    assert dict(response.metadata) == {}


def test_execution_response_metadata_cannot_be_mutated():
    response = ExecutionResponse(success=True, metadata={"a": 1})

    with pytest.raises(TypeError):
        response.metadata["a"] = 2


def test_execution_response_is_frozen():
    response = ExecutionResponse(success=True)

    with pytest.raises(dataclasses.FrozenInstanceError):
        response.success = False


# --- state (Task 1: execution lifecycle) --------------------------------------


def test_execution_response_state_defaults_to_completed_on_success():
    response = ExecutionResponse(success=True)

    assert response.state == ExecutionState.COMPLETED


def test_execution_response_state_defaults_to_failed_on_failure():
    response = ExecutionResponse(success=False, error="something broke")

    assert response.state == ExecutionState.FAILED


def test_execution_response_state_can_be_explicitly_overridden():
    response = ExecutionResponse(success=False, state=ExecutionState.CANCELLED)

    assert response.state == ExecutionState.CANCELLED


def test_execution_response_explicit_state_is_not_overwritten_by_the_default():
    response = ExecutionResponse(success=True, state=ExecutionState.RETRYING)

    assert response.state == ExecutionState.RETRYING


def test_execution_response_state_is_never_none_after_construction():
    assert ExecutionResponse(success=True).state is not None
    assert ExecutionResponse(success=False).state is not None
