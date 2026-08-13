import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.kernel.cancellation import CancellationReason
from app.services.ai.kernel.events import (
    CapabilityResolved,
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionRetried,
    ExecutionStarted,
    KernelEvent,
    ProviderResolved,
)
from app.services.ai.kernel.state import ExecutionState


def test_execution_started_construction():
    event = ExecutionStarted(request_id="req-1", capability="conversation")

    assert event.request_id == "req-1"
    assert event.capability == "conversation"


def test_execution_id_defaults_to_none_for_backward_compatibility():
    event = ExecutionStarted(request_id="req-1", capability="conversation")

    assert event.execution_id is None


def test_execution_id_can_be_set_and_is_distinct_from_request_id():
    event = ExecutionStarted(request_id="req-1", capability="conversation", execution_id="exec-1")

    assert event.execution_id == "exec-1"
    assert event.execution_id != event.request_id


def test_execution_completed_construction():
    event = ExecutionCompleted(request_id="req-1", state=ExecutionState.COMPLETED)

    assert event.state == ExecutionState.COMPLETED


def test_execution_failed_construction():
    event = ExecutionFailed(request_id="req-1", error="provider unavailable")

    assert event.error == "provider unavailable"


def test_execution_cancelled_construction():
    event = ExecutionCancelled(request_id="req-1", reason=CancellationReason.USER_REQUESTED)

    assert event.reason == CancellationReason.USER_REQUESTED


def test_execution_retried_construction():
    event = ExecutionRetried(request_id="req-1", attempt=2)

    assert event.attempt == 2


def test_provider_resolved_construction():
    event = ProviderResolved(request_id="req-1", provider="openai")

    assert event.provider == "openai"


def test_capability_resolved_construction():
    event = CapabilityResolved(request_id="req-1", capability="conversation")

    assert event.capability == "conversation"


@pytest.mark.parametrize(
    "event",
    [
        ExecutionStarted(request_id="req-1", capability="conversation"),
        ExecutionCompleted(request_id="req-1", state=ExecutionState.COMPLETED),
        ExecutionFailed(request_id="req-1", error="boom"),
        ExecutionCancelled(request_id="req-1", reason=CancellationReason.TIMEOUT),
        ExecutionRetried(request_id="req-1", attempt=1),
        ProviderResolved(request_id="req-1", provider="openai"),
        CapabilityResolved(request_id="req-1", capability="conversation"),
    ],
)
def test_every_event_is_a_member_of_the_kernel_event_union(event):
    assert isinstance(event, KernelEvent)


@pytest.mark.parametrize(
    "event",
    [
        ExecutionStarted(request_id="req-1", capability="conversation"),
        ExecutionCompleted(request_id="req-1", state=ExecutionState.COMPLETED),
        ExecutionFailed(request_id="req-1", error="boom"),
        ExecutionCancelled(request_id="req-1", reason=CancellationReason.TIMEOUT),
        ExecutionRetried(request_id="req-1", attempt=1),
        ProviderResolved(request_id="req-1", provider="openai"),
        CapabilityResolved(request_id="req-1", capability="conversation"),
    ],
)
def test_every_event_metadata_defaults_to_empty_read_only_mapping(event):
    assert isinstance(event.metadata, MappingProxyType)
    assert dict(event.metadata) == {}


@pytest.mark.parametrize(
    "event",
    [
        ExecutionStarted(request_id="req-1", capability="conversation", metadata={"x": 1}),
        ExecutionCompleted(request_id="req-1", state=ExecutionState.COMPLETED, metadata={"x": 1}),
        ExecutionFailed(request_id="req-1", error="boom", metadata={"x": 1}),
    ],
)
def test_event_metadata_cannot_be_mutated(event):
    with pytest.raises(TypeError):
        event.metadata["x"] = 2


@pytest.mark.parametrize(
    "event",
    [
        ExecutionStarted(request_id="req-1", capability="conversation"),
        ExecutionFailed(request_id="req-1", error="boom"),
    ],
)
def test_events_are_frozen(event):
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.request_id = "changed"
