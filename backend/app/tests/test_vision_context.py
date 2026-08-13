import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.vision.context import VisionContext


def test_defaults():
    context = VisionContext()

    assert context.agent_id is None
    assert context.capability_category is None
    assert isinstance(context.execution_id, str) and context.execution_id


def test_composes_a_shared_execution_context_by_default():
    context = VisionContext()

    assert isinstance(context.shared, SharedExecutionContext)


def test_an_explicit_shared_context_can_be_passed_through():
    shared = SharedExecutionContext(organization_id=9)

    context = VisionContext(shared=shared, agent_id="agent-1")

    assert context.shared is shared
    assert context.organization_id == 9
    assert context.agent_id == "agent-1"


def test_flat_kwargs_forward_into_a_freshly_built_shared_context():
    context = VisionContext(organization_id=5, session_id="s1")

    assert context.organization_id == 5
    assert context.session_id == "s1"


def test_delegates_correlation_and_causation_ids():
    shared = SharedExecutionContext(causation_id="cause-1", parent_execution_id="parent-1")

    context = VisionContext(shared=shared)

    assert context.correlation_id == shared.correlation_id
    assert context.causation_id == "cause-1"
    assert context.parent_execution_id == "parent-1"


def test_capability_category_is_vision_specific():
    context = VisionContext(capability_category="image")

    assert context.capability_category == "image"


def test_metadata_defaults_to_empty_read_only_mapping():
    assert isinstance(VisionContext().metadata, MappingProxyType)


def test_metadata_cannot_be_mutated():
    context = VisionContext(metadata={"a": 1})

    with pytest.raises(TypeError):
        context.metadata["a"] = 2


def test_is_frozen():
    context = VisionContext()

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.agent_id = "changed"


def test_never_duplicates_execution_identity():
    field_names = {f.name for f in dataclasses.fields(VisionContext)}

    assert field_names == {"shared", "agent_id", "capability_category", "metadata"}
