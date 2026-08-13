import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.runtime.cancellation import CancellationToken
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.tools.context import ToolContext


def test_defaults():
    context = ToolContext("fake-tool")

    assert context.tool_id == "fake-tool"
    assert context.agent_id is None
    assert context.workflow_id is None
    assert context.execution_depth == 0
    assert dict(context.parameters) == {}
    assert context.cancellation_token is None


def test_composes_a_shared_execution_context_by_default():
    context = ToolContext("fake-tool")

    assert isinstance(context.shared, SharedExecutionContext)
    assert isinstance(context.execution_id, str) and context.execution_id


def test_an_explicit_shared_context_can_be_passed_through():
    shared = SharedExecutionContext(organization_id=9)

    context = ToolContext("fake-tool", shared=shared)

    assert context.shared is shared
    assert context.organization_id == 9


def test_flat_kwargs_forward_into_a_freshly_built_shared_context():
    context = ToolContext("fake-tool", organization_id=5, session_id="s1")

    assert context.organization_id == 5
    assert context.session_id == "s1"


def test_delegates_correlation_and_causation_ids():
    shared = SharedExecutionContext(causation_id="cause-1", parent_execution_id="parent-1")

    context = ToolContext("fake-tool", shared=shared)

    assert context.correlation_id == shared.correlation_id
    assert context.causation_id == "cause-1"
    assert context.parent_execution_id == "parent-1"


def test_agent_id_and_workflow_id_and_execution_depth_are_tool_specific():
    context = ToolContext("fake-tool", agent_id="agent-1", workflow_id="wf-1", execution_depth=3)

    assert context.agent_id == "agent-1"
    assert context.workflow_id == "wf-1"
    assert context.execution_depth == 3


def test_parameters_defaults_to_empty_read_only_mapping():
    assert isinstance(ToolContext("fake-tool").parameters, MappingProxyType)


def test_parameters_cannot_be_mutated():
    context = ToolContext("fake-tool", parameters={"query": "hi"})

    with pytest.raises(TypeError):
        context.parameters["query"] = "changed"


def test_metadata_defaults_to_empty_read_only_mapping_and_is_immutable():
    context = ToolContext("fake-tool", metadata={"a": 1})

    assert isinstance(context.metadata, MappingProxyType)
    with pytest.raises(TypeError):
        context.metadata["a"] = 2


def test_cancellation_token_can_be_supplied():
    token = CancellationToken()

    context = ToolContext("fake-tool", cancellation_token=token)

    assert context.cancellation_token is token


def test_is_frozen():
    context = ToolContext("fake-tool")

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.execution_depth = 1


def test_never_duplicates_runtime_or_agent_specific_fields():
    field_names = {f.name for f in dataclasses.fields(ToolContext)}

    assert field_names == {
        "shared",
        "tool_id",
        "agent_id",
        "workflow_id",
        "execution_depth",
        "parameters",
        "metadata",
        "cancellation_token",
    }
