import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.kernel.cancellation import (
    CancellationPolicy,
    CancellationReason,
    ExecutionCancellation,
)


# --- CancellationReason ---------------------------------------------------------


def test_cancellation_reason_values():
    assert CancellationReason.USER_REQUESTED == "user_requested"
    assert CancellationReason.TIMEOUT == "timeout"
    assert CancellationReason.SUPERSEDED == "superseded"
    assert CancellationReason.SYSTEM_SHUTDOWN == "system_shutdown"
    assert CancellationReason.POLICY_VIOLATION == "policy_violation"
    assert CancellationReason.UNKNOWN == "unknown"


def test_cancellation_reason_members_are_all_distinct():
    values = [member.value for member in CancellationReason]
    assert len(values) == len(set(values))


# --- CancellationPolicy ---------------------------------------------------------


def test_cancellation_policy_defaults():
    policy = CancellationPolicy()

    assert policy.allow_cancellation is True
    assert policy.grace_period_ms is None
    assert policy.propagate_to_children is True


def test_cancellation_policy_construction_with_all_fields():
    policy = CancellationPolicy(allow_cancellation=False, grace_period_ms=5000, propagate_to_children=False)

    assert policy.allow_cancellation is False
    assert policy.grace_period_ms == 5000
    assert policy.propagate_to_children is False


def test_cancellation_policy_is_frozen():
    policy = CancellationPolicy()

    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.allow_cancellation = False


# --- ExecutionCancellation -------------------------------------------------------


def test_execution_cancellation_construction():
    cancellation = ExecutionCancellation(request_id="req-1", reason=CancellationReason.USER_REQUESTED)

    assert cancellation.request_id == "req-1"
    assert cancellation.reason == CancellationReason.USER_REQUESTED


def test_execution_cancellation_metadata_defaults_to_empty_read_only_mapping():
    cancellation = ExecutionCancellation(request_id="req-1", reason=CancellationReason.TIMEOUT)

    assert isinstance(cancellation.metadata, MappingProxyType)
    assert dict(cancellation.metadata) == {}


def test_execution_cancellation_metadata_cannot_be_mutated():
    cancellation = ExecutionCancellation(
        request_id="req-1", reason=CancellationReason.TIMEOUT, metadata={"x": 1}
    )

    with pytest.raises(TypeError):
        cancellation.metadata["x"] = 2


def test_execution_cancellation_is_frozen():
    cancellation = ExecutionCancellation(request_id="req-1", reason=CancellationReason.TIMEOUT)

    with pytest.raises(dataclasses.FrozenInstanceError):
        cancellation.reason = CancellationReason.SUPERSEDED
