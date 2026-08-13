import dataclasses
from datetime import datetime
from types import MappingProxyType

import pytest

from app.services.ai.shared.execution_context import SharedExecutionContext


# --- identity defaults --------------------------------------------------------------


def test_execution_id_is_auto_generated():
    context = SharedExecutionContext()

    assert isinstance(context.execution_id, str) and context.execution_id


def test_two_instances_get_different_execution_ids():
    assert SharedExecutionContext().execution_id != SharedExecutionContext().execution_id


def test_request_id_is_auto_generated_independently_of_execution_id():
    context = SharedExecutionContext()

    assert isinstance(context.request_id, str) and context.request_id
    assert context.request_id != context.execution_id


def test_created_at_defaults_to_a_datetime():
    context = SharedExecutionContext()

    assert isinstance(context.created_at, datetime)


def test_optional_identity_fields_default_to_none():
    context = SharedExecutionContext()

    assert context.parent_execution_id is None
    assert context.causation_id is None
    assert context.session_id is None
    assert context.organization_id is None
    assert context.user_id is None
    assert context.conversation_id is None


# --- correlation_id / causation_id ----------------------------------------------------


def test_correlation_id_defaults_to_this_contexts_own_execution_id():
    context = SharedExecutionContext()

    assert context.correlation_id == context.execution_id


def test_explicit_correlation_id_is_respected():
    context = SharedExecutionContext(correlation_id="corr-1")

    assert context.correlation_id == "corr-1"
    assert context.correlation_id != context.execution_id


def test_causation_id_stays_none_unless_explicitly_given():
    assert SharedExecutionContext().causation_id is None


def test_explicit_causation_id_is_respected():
    context = SharedExecutionContext(causation_id="cause-1")

    assert context.causation_id == "cause-1"


# --- parent execution / execution tree -------------------------------------------------


def test_root_context_has_no_parent():
    assert SharedExecutionContext().parent_execution_id is None


def test_explicit_parent_execution_id_is_respected():
    context = SharedExecutionContext(parent_execution_id="parent-1")

    assert context.parent_execution_id == "parent-1"


def test_child_sets_parent_execution_id_to_the_parents_execution_id():
    parent = SharedExecutionContext()

    child = parent.child()

    assert child.parent_execution_id == parent.execution_id


def test_child_gets_a_fresh_execution_id_and_request_id():
    parent = SharedExecutionContext()

    child = parent.child()

    assert child.execution_id != parent.execution_id
    assert child.request_id != parent.request_id


def test_child_sets_causation_id_to_the_parents_execution_id():
    parent = SharedExecutionContext()

    child = parent.child()

    assert child.causation_id == parent.execution_id


def test_child_propagates_correlation_id_by_default():
    parent = SharedExecutionContext()

    child = parent.child()

    assert child.correlation_id == parent.correlation_id


def test_child_propagates_session_and_tenant_identity():
    parent = SharedExecutionContext(session_id="sess-1", organization_id=7, user_id=42, conversation_id=99)

    child = parent.child()

    assert child.session_id == "sess-1"
    assert child.organization_id == 7
    assert child.user_id == 42
    assert child.conversation_id == 99


def test_child_accepts_explicit_overrides():
    parent = SharedExecutionContext()

    child = parent.child(correlation_id="new-correlation")

    assert child.correlation_id == "new-correlation"


def test_a_deep_execution_tree_shares_one_correlation_id():
    # Executive -> Agent -> Sub-Agent -> Tool -> Runtime
    executive = SharedExecutionContext()
    agent = executive.child()
    sub_agent = agent.child()
    tool = sub_agent.child()
    runtime = tool.child()

    assert {executive.correlation_id, agent.correlation_id, sub_agent.correlation_id, tool.correlation_id, runtime.correlation_id} == {
        executive.correlation_id
    }
    assert runtime.parent_execution_id == tool.execution_id
    assert tool.parent_execution_id == sub_agent.execution_id
    assert sub_agent.parent_execution_id == agent.execution_id
    assert agent.parent_execution_id == executive.execution_id
    assert executive.parent_execution_id is None


# --- metadata: genuine read-only mapping, no mutable collections --------------------------


def test_metadata_defaults_to_an_empty_read_only_mapping():
    context = SharedExecutionContext()

    assert isinstance(context.metadata, MappingProxyType)
    assert dict(context.metadata) == {}


def test_metadata_passed_as_plain_dict_is_coerced_to_read_only():
    context = SharedExecutionContext(metadata={"a": 1})

    assert isinstance(context.metadata, MappingProxyType)


def test_metadata_cannot_be_mutated():
    context = SharedExecutionContext(metadata={"a": 1})

    with pytest.raises(TypeError):
        context.metadata["a"] = 2


def test_mutating_the_original_dict_after_construction_does_not_affect_the_context():
    original = {"a": 1}
    context = SharedExecutionContext(metadata=original)

    original["a"] = 999

    assert dict(context.metadata) == {"a": 1}


# --- immutability --------------------------------------------------------------------


def test_execution_id_never_changes():
    context = SharedExecutionContext()
    original_id = context.execution_id

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.execution_id = "changed"

    assert context.execution_id == original_id


def test_every_field_is_frozen():
    context = SharedExecutionContext()

    for field_name in ("parent_execution_id", "correlation_id", "causation_id", "session_id", "organization_id"):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(context, field_name, "changed")


# --- equality ---------------------------------------------------------------------------


def test_two_contexts_with_identical_fields_are_equal():
    now = datetime.now()
    first = SharedExecutionContext(execution_id="exec-1", request_id="req-1", created_at=now)
    second = SharedExecutionContext(execution_id="exec-1", request_id="req-1", created_at=now)

    assert first == second


def test_two_contexts_with_different_execution_ids_are_not_equal():
    assert SharedExecutionContext() != SharedExecutionContext()


def test_equality_is_deterministic_across_repeated_comparisons():
    now = datetime.now()
    first = SharedExecutionContext(execution_id="exec-1", request_id="req-1", created_at=now)
    second = SharedExecutionContext(execution_id="exec-1", request_id="req-1", created_at=now)

    assert (first == second) == (first == second) is True


# --- hashing -----------------------------------------------------------------------------


def test_context_is_hashable():
    context = SharedExecutionContext()

    assert isinstance(hash(context), int)


def test_hash_is_stable_across_repeated_calls():
    context = SharedExecutionContext()

    assert hash(context) == hash(context)


def test_equal_contexts_hash_equal():
    first = SharedExecutionContext(execution_id="exec-1", request_id="req-1")
    second = SharedExecutionContext(execution_id="exec-1", request_id="req-1")

    assert hash(first) == hash(second)


def test_context_can_be_used_as_a_set_member_or_dict_key():
    context = SharedExecutionContext()

    registry = {context: "value"}

    assert registry[context] == "value"
    assert context in {context}
