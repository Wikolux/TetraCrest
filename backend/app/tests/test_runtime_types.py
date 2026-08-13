import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.conversation.types import ConversationResponse
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.types import (
    AIRuntimeError,
    EventType,
    RuntimeContext,
    RuntimeEvent,
    RuntimeExecutionResult,
    RuntimeRequest,
    RuntimeResponse,
)
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.shared.execution_metadata import ExecutionMetadata
from app.services.ai.shared.response import AIResponseMetadata, ProviderResponse, UsageDetails
from app.services.prompt_builder.types import PromptPackage


def _prompt_package():
    return PromptPackage(system_prompt="system")


def _conversation_response():
    return ConversationResponse(
        text="hello",
        response=ProviderResponse(
            metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="gpt-fake"),
            usage=UsageDetails(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        ),
    )


# --- AIRuntimeError -----------------------------------------------------------------


def test_ai_runtime_error_is_an_exception():
    assert issubclass(AIRuntimeError, Exception)


def test_ai_runtime_error_can_be_raised_and_caught():
    with pytest.raises(AIRuntimeError, match="boom"):
        raise AIRuntimeError("boom")


# --- EventType ------------------------------------------------------------------------


def test_event_type_has_every_documented_kind():
    assert {member.value for member in EventType} == {
        "started",
        "provider_selected",
        "request_sent",
        "response_received",
        "completed",
        "failed",
        "cancelled",
        "timeout",
    }


# --- RuntimeEvent -----------------------------------------------------------------------


def test_runtime_event_construction():
    event = RuntimeEvent(event_type=EventType.STARTED, execution_id="exec-1")

    assert event.event_type == EventType.STARTED
    assert event.execution_id == "exec-1"


def test_runtime_event_data_defaults_to_empty_read_only_mapping():
    event = RuntimeEvent(event_type=EventType.STARTED, execution_id="exec-1")

    assert isinstance(event.data, MappingProxyType)
    assert dict(event.data) == {}


def test_runtime_event_data_cannot_be_mutated():
    event = RuntimeEvent(event_type=EventType.STARTED, execution_id="exec-1", data={"a": 1})

    with pytest.raises(TypeError):
        event.data["a"] = 2


def test_runtime_event_is_frozen():
    event = RuntimeEvent(event_type=EventType.STARTED, execution_id="exec-1")

    with pytest.raises(dataclasses.FrozenInstanceError):
        event.execution_id = "changed"


# --- RuntimeContext ---------------------------------------------------------------------


def test_runtime_context_defaults():
    context = RuntimeContext()

    assert context.attempt == 1
    assert context.retry_count == 0
    assert context.provider is None
    assert context.provider_model is None
    assert context.timeout is None
    assert isinstance(context.execution_id, str) and context.execution_id
    assert isinstance(context.request_id, str) and context.request_id


def test_runtime_context_composes_a_shared_execution_context():
    context = RuntimeContext()

    assert isinstance(context.shared, SharedExecutionContext)


def test_runtime_context_exposes_correlation_and_causation_via_delegating_properties():
    shared = SharedExecutionContext(causation_id="cause-1", parent_execution_id="parent-1")

    context = RuntimeContext(shared=shared)

    assert context.correlation_id == shared.correlation_id
    assert context.causation_id == "cause-1"
    assert context.parent_execution_id == "parent-1"


def test_runtime_context_two_instances_get_different_ids():
    assert RuntimeContext().execution_id != RuntimeContext().execution_id


def test_runtime_context_is_frozen():
    context = RuntimeContext()

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.attempt = 2


def test_runtime_context_replace_produces_a_new_instance_with_updated_attempt():
    context = RuntimeContext()

    next_context = dataclasses.replace(context, attempt=2)

    assert next_context.attempt == 2
    assert context.attempt == 1
    assert next_context.execution_id == context.execution_id


def test_runtime_context_metadata_is_read_only():
    context = RuntimeContext(shared=SharedExecutionContext(metadata={"b": 2}))

    assert isinstance(context.metadata, MappingProxyType)
    with pytest.raises(TypeError):
        context.metadata["b"] = 3


def test_runtime_context_runtime_metadata_defaults_to_an_execution_metadata_instance():
    context = RuntimeContext()

    assert isinstance(context.runtime_metadata, ExecutionMetadata)


# --- RuntimeRequest ---------------------------------------------------------------------


def test_runtime_request_construction_with_required_fields_only():
    request = RuntimeRequest(
        organization_id=1,
        prompt_package=_prompt_package(),
        provider=ProviderName.OPENAI,
    )

    assert request.organization_id == 1
    assert request.provider == ProviderName.OPENAI
    assert request.conversation_id is None
    assert request.stream is False
    assert request.cancellation_token is None


def test_runtime_request_is_frozen():
    request = RuntimeRequest(organization_id=1, prompt_package=_prompt_package(), provider=ProviderName.OPENAI)

    with pytest.raises(dataclasses.FrozenInstanceError):
        request.organization_id = 2


def test_runtime_request_metadata_defaults_to_empty_read_only_mapping():
    request = RuntimeRequest(organization_id=1, prompt_package=_prompt_package(), provider=ProviderName.OPENAI)

    assert isinstance(request.metadata, MappingProxyType)


# --- RuntimeExecutionResult ---------------------------------------------------------------


def test_runtime_execution_result_defaults():
    result = RuntimeExecutionResult(success=True)

    assert result.attempt == 1
    assert result.retryable is True
    assert result.conversation_response is None
    assert result.error is None


def test_runtime_execution_result_is_frozen():
    result = RuntimeExecutionResult(success=True)

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.success = False


# --- RuntimeResponse ----------------------------------------------------------------------


def test_runtime_response_success_construction():
    response = RuntimeResponse(
        success=True,
        provider=ProviderName.OPENAI,
        conversation_response=_conversation_response(),
        latency_ms=12.5,
    )

    assert response.success is True
    assert response.conversation_response.text == "hello"
    assert response.error is None


def test_runtime_response_failure_construction():
    response = RuntimeResponse(success=False, error="boom")

    assert response.success is False
    assert response.conversation_response is None
    assert response.error == "boom"


def test_runtime_response_events_and_warnings_default_to_empty_tuples():
    response = RuntimeResponse(success=True)

    assert response.events == ()
    assert response.warnings == ()


def test_runtime_response_is_frozen():
    response = RuntimeResponse(success=True)

    with pytest.raises(dataclasses.FrozenInstanceError):
        response.success = False


# --- RuntimeResponse: execution identity (M16.6) -----------------------------------------


def test_runtime_response_carries_identity_fields_copied_from_a_context():
    shared = SharedExecutionContext(parent_execution_id="parent-1", causation_id="cause-1")

    response = RuntimeResponse(success=True, **shared.identity_fields())

    assert response.execution_id == shared.execution_id
    assert response.parent_execution_id == "parent-1"
    assert response.correlation_id == shared.correlation_id
    assert response.causation_id == "cause-1"


def test_runtime_response_identity_defaults_are_never_empty():
    response = RuntimeResponse(success=True)

    assert response.execution_id
    assert response.correlation_id
    assert response.parent_execution_id is None
    assert response.causation_id is None
