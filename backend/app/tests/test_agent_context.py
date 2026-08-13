import dataclasses
from datetime import datetime
from types import MappingProxyType

import pytest

from app.services.ai.agents.context import AgentContext
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.shared.execution_metadata import ExecutionMetadata


def test_agent_context_defaults():
    context = AgentContext()

    assert isinstance(context.execution_id, str) and context.execution_id
    assert isinstance(context.request_id, str) and context.request_id
    assert context.session_id is None
    assert context.organization_id is None
    assert context.user_id is None
    assert context.conversation_id is None
    assert isinstance(context.created_at, datetime)


def test_agent_context_two_instances_get_different_ids():
    first, second = AgentContext(), AgentContext()

    assert first.execution_id != second.execution_id
    assert first.request_id != second.request_id


def test_agent_context_accepts_explicit_fields():
    context = AgentContext(organization_id=1, user_id=2, conversation_id=3, session_id="sess-1")

    assert context.organization_id == 1
    assert context.user_id == 2
    assert context.conversation_id == 3
    assert context.session_id == "sess-1"


def test_agent_context_is_frozen():
    context = AgentContext()

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.organization_id = 5


def test_agent_context_metadata_defaults_to_empty_read_only_mapping():
    context = AgentContext()

    assert isinstance(context.metadata, MappingProxyType)


def test_agent_context_metadata_cannot_be_mutated():
    context = AgentContext(metadata={"a": 1})

    with pytest.raises(TypeError):
        context.metadata["a"] = 2


# --- composition: AgentContext wraps SharedExecutionContext -------------------------


def test_agent_context_composes_a_shared_execution_context_by_default():
    context = AgentContext()

    assert isinstance(context.shared, SharedExecutionContext)


def test_an_explicit_shared_context_can_be_passed_through():
    shared = SharedExecutionContext(organization_id=9)

    context = AgentContext(shared=shared, agent_id="agent-1")

    assert context.shared is shared
    assert context.organization_id == 9


def test_agent_context_exposes_correlation_and_causation_via_delegating_properties():
    shared = SharedExecutionContext(causation_id="cause-1", parent_execution_id="parent-1")

    context = AgentContext(shared=shared)

    assert context.correlation_id == shared.correlation_id
    assert context.causation_id == "cause-1"
    assert context.parent_execution_id == "parent-1"


def test_flat_kwargs_and_shared_kwarg_produce_equivalent_identity():
    via_flat_kwargs = AgentContext(organization_id=5, session_id="s1")
    via_shared = AgentContext(shared=SharedExecutionContext(organization_id=5, session_id="s1"))

    assert via_flat_kwargs.organization_id == via_shared.organization_id
    assert via_flat_kwargs.session_id == via_shared.session_id


# --- agent-specific fields ----------------------------------------------------------------


def test_agent_specific_fields_default():
    context = AgentContext()

    assert context.agent_id is None
    assert context.workflow_id is None
    assert context.parent_agent_id is None
    assert context.delegation_depth == 0
    assert isinstance(context.agent_metadata, ExecutionMetadata)


def test_agent_specific_fields_can_be_set():
    context = AgentContext(
        agent_id="agent-1", workflow_id="wf-1", parent_agent_id="agent-0", delegation_depth=2
    )

    assert context.agent_id == "agent-1"
    assert context.workflow_id == "wf-1"
    assert context.parent_agent_id == "agent-0"
    assert context.delegation_depth == 2


def test_agent_context_never_duplicates_runtime_concerns():
    # RuntimeContext-only concerns (provider, attempt, timeout, ...) have
    # no place on AgentContext
    for runtime_only_field in ("provider", "attempt", "retry_count", "timeout"):
        assert not hasattr(AgentContext, runtime_only_field)


# --- execution tree via the composed SharedExecutionContext --------------------------------


def test_a_child_agent_context_can_be_built_from_the_parents_shared_context():
    parent = AgentContext(agent_id="agent-0")

    child = AgentContext(shared=parent.shared.child(), agent_id="agent-1", parent_agent_id="agent-0")

    assert child.shared.parent_execution_id == parent.execution_id
    assert child.shared.correlation_id == parent.shared.correlation_id
    assert child.parent_agent_id == "agent-0"
