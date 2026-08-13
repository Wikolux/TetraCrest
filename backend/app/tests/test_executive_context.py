import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.executive.context import ExecutiveContext
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.prompt_builder.types import PromptMessage


def test_defaults():
    agent_context = AgentContext(organization_id=1)

    context = ExecutiveContext(agent_context=agent_context)

    assert context.user_request == ""
    assert context.conversation_history == ()
    assert context.agent_context is agent_context


def test_delegates_execution_identity_to_the_agent_context():
    agent_context = AgentContext(organization_id=1)

    context = ExecutiveContext(agent_context=agent_context)

    assert context.execution_id == agent_context.execution_id
    assert context.correlation_id == agent_context.correlation_id
    assert context.causation_id == agent_context.causation_id
    assert context.organization_id == 1
    assert isinstance(context.shared, SharedExecutionContext)
    assert context.shared is agent_context.shared


def test_conversation_id_delegates_to_the_agent_context():
    agent_context = AgentContext(organization_id=1, conversation_id=42)

    context = ExecutiveContext(agent_context=agent_context)

    assert context.conversation_id == 42


def test_shared_is_a_computed_property_not_a_stored_field():
    # execution identity must exist exactly once - `shared` is reached via
    # a property delegating to agent_context.shared, never stored as its
    # own dataclass field on ExecutiveContext
    field_names = {f.name for f in dataclasses.fields(ExecutiveContext)}

    assert "shared" not in field_names
    assert field_names == {"agent_context", "user_request", "conversation_history", "metadata"}


def test_conversation_history_is_coerced_to_a_tuple():
    history = [PromptMessage(role="user", content="hi")]

    context = ExecutiveContext(agent_context=AgentContext(), conversation_history=history)

    assert context.conversation_history == (PromptMessage(role="user", content="hi"),)


def test_metadata_defaults_to_empty_read_only_mapping():
    assert isinstance(ExecutiveContext(agent_context=AgentContext()).metadata, MappingProxyType)


def test_metadata_cannot_be_mutated():
    context = ExecutiveContext(agent_context=AgentContext(), metadata={"a": 1})

    with pytest.raises(TypeError):
        context.metadata["a"] = 2


def test_is_frozen():
    context = ExecutiveContext(agent_context=AgentContext())

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.user_request = "changed"
