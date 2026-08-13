import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.kernel.context import ExecutionContext
from app.services.ai.shared.execution_context import SharedExecutionContext


def test_request_id_is_auto_generated_when_not_supplied():
    context = ExecutionContext()

    assert isinstance(context.request_id, str)
    assert context.request_id != ""


def test_request_id_is_unique_per_instance():
    first = ExecutionContext()
    second = ExecutionContext()

    assert first.request_id != second.request_id


def test_explicit_request_id_is_respected():
    context = ExecutionContext(request_id="req-123")

    assert context.request_id == "req-123"


def test_all_identity_fields_default_to_none():
    context = ExecutionContext()

    assert context.organization_id is None
    assert context.user_id is None
    assert context.session_id is None
    assert context.agent_id is None
    assert context.capability is None


def test_construction_with_all_fields():
    context = ExecutionContext(
        request_id="req-1",
        organization_id=7,
        user_id=42,
        session_id="sess-1",
        agent_id="agent-1",
        capability="conversation",
        metadata={"key": "value"},
    )

    assert context.organization_id == 7
    assert context.user_id == 42
    assert context.session_id == "sess-1"
    assert context.agent_id == "agent-1"
    assert context.capability == "conversation"
    assert context.metadata == {"key": "value"}


def test_capability_is_a_plain_string_field():
    context = ExecutionContext(capability="conversation")

    assert isinstance(context.capability, str)


# --- composition: ExecutionContext wraps SharedExecutionContext ------------------


def test_execution_context_composes_a_shared_execution_context_by_default():
    context = ExecutionContext()

    assert isinstance(context.shared, SharedExecutionContext)
    assert isinstance(context.execution_id, str) and context.execution_id


def test_execution_context_exposes_correlation_and_causation_via_delegating_properties():
    shared = SharedExecutionContext(causation_id="cause-1", parent_execution_id="parent-1")

    context = ExecutionContext(shared=shared)

    assert context.correlation_id == shared.correlation_id
    assert context.causation_id == "cause-1"
    assert context.parent_execution_id == "parent-1"


def test_an_explicit_shared_context_can_be_passed_through():
    shared = SharedExecutionContext(organization_id=9)

    context = ExecutionContext(shared=shared, capability="conversation")

    assert context.shared is shared
    assert context.organization_id == 9


def test_flat_kwargs_and_shared_kwarg_are_mutually_exclusive_conveniences():
    # the flat kwargs (request_id=, organization_id=, ...) are a
    # backward-compatible shortcut for building a `shared` - both paths
    # produce the same field values
    via_flat_kwargs = ExecutionContext(organization_id=5, session_id="s1")
    via_shared = ExecutionContext(shared=SharedExecutionContext(organization_id=5, session_id="s1"))

    assert via_flat_kwargs.organization_id == via_shared.organization_id
    assert via_flat_kwargs.session_id == via_shared.session_id


# --- metadata: genuine read-only mapping ---------------------------------


def test_metadata_defaults_to_an_empty_read_only_mapping():
    context = ExecutionContext()

    assert isinstance(context.metadata, MappingProxyType)
    assert dict(context.metadata) == {}


def test_metadata_passed_as_plain_dict_is_coerced_to_read_only():
    context = ExecutionContext(metadata={"a": 1})

    assert isinstance(context.metadata, MappingProxyType)


def test_metadata_cannot_be_mutated():
    context = ExecutionContext(metadata={"a": 1})

    with pytest.raises(TypeError):
        context.metadata["a"] = 2


def test_mutating_the_original_dict_after_construction_does_not_affect_the_context():
    original = {"a": 1}
    context = ExecutionContext(metadata=original)

    original["a"] = 999
    original["b"] = 2

    assert dict(context.metadata) == {"a": 1}


# --- immutability ------------------------------------------------------------


def test_execution_context_is_frozen():
    context = ExecutionContext()

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.organization_id = 7


def test_execution_context_capability_cannot_be_reassigned():
    context = ExecutionContext(capability="conversation")

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.capability = "vision"
