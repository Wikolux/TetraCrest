import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.request import SpecialistRequest
from app.services.ai.shared.execution_context import SharedExecutionContext


def test_defaults():
    agent_context = AgentContext(organization_id=1)

    context = SpecialistContext(agent_context=agent_context)

    assert context.request is None
    assert context.agent_context is agent_context


def test_delegates_execution_identity_to_the_agent_context():
    agent_context = AgentContext(organization_id=1, conversation_id=7)

    context = SpecialistContext(agent_context=agent_context)

    assert context.execution_id == agent_context.execution_id
    assert context.correlation_id == agent_context.correlation_id
    assert context.causation_id == agent_context.causation_id
    assert context.parent_execution_id == agent_context.parent_execution_id
    assert context.organization_id == 1
    assert context.conversation_id == 7
    assert context.agent_id == agent_context.agent_id
    assert isinstance(context.shared, SharedExecutionContext)
    assert context.shared is agent_context.shared


def test_holds_the_specialist_request():
    request = SpecialistRequest(objective="Prepare for an interview")

    context = SpecialistContext(agent_context=AgentContext(), request=request)

    assert context.request is request


def test_shared_is_a_computed_property_not_a_stored_field():
    field_names = {f.name for f in dataclasses.fields(SpecialistContext)}

    assert "shared" not in field_names
    assert field_names == {"agent_context", "request", "metadata"}


def test_metadata_defaults_to_empty_read_only_mapping():
    assert isinstance(SpecialistContext(agent_context=AgentContext()).metadata, MappingProxyType)


def test_metadata_cannot_be_mutated():
    context = SpecialistContext(agent_context=AgentContext(), metadata={"a": 1})

    with pytest.raises(TypeError):
        context.metadata["a"] = 2


def test_is_frozen():
    context = SpecialistContext(agent_context=AgentContext())

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.request = None
