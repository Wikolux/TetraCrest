import dataclasses
from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.enums import AgentCapability, AgentState
from app.services.ai.agents.types import AgentError, AgentExecutionResult, AgentIdentity, AgentPermissionError
from app.services.ai.shared.execution_context import SharedExecutionContext


def test_agent_permission_error_is_an_agent_error():
    assert issubclass(AgentPermissionError, AgentError)


# --- AgentIdentity ------------------------------------------------------------------


def test_agent_identity_construction_with_required_fields_only():
    identity = AgentIdentity(agent_id="agent-1", name="research", display_name="Research Agent")

    assert identity.agent_id == "agent-1"
    assert identity.version == "1.0"
    assert identity.owner is None
    assert identity.permissions == ()
    assert identity.capabilities == AgentCapabilities()


def test_agent_identity_accepts_declared_capabilities_and_permissions():
    identity = AgentIdentity(
        agent_id="agent-1",
        name="research",
        display_name="Research Agent",
        capabilities=AgentCapabilities(declared={AgentCapability.RESEARCH}),
        permissions=("memory:read", "tools:execute"),
    )

    assert identity.capabilities.has(AgentCapability.RESEARCH) is True
    assert identity.permissions == ("memory:read", "tools:execute")


def test_agent_identity_is_frozen():
    identity = AgentIdentity(agent_id="agent-1", name="research", display_name="Research Agent")

    with pytest.raises(dataclasses.FrozenInstanceError):
        identity.agent_id = "changed"


def test_agent_identity_has_no_mutable_state_field():
    # state deliberately lives on AgentStateMachine, not on identity
    assert not hasattr(AgentIdentity, "state")


# --- AgentExecutionResult -----------------------------------------------------------


def _result(**overrides):
    now = datetime.now(UTC)
    defaults = dict(
        agent_id="agent-1",
        state=AgentState.READY,
        started_at=now,
        completed_at=now,
        duration_ms=1.0,
    )
    defaults.update(overrides)
    return AgentExecutionResult(**defaults)


def test_agent_execution_result_construction():
    result = _result()

    assert result.agent_id == "agent-1"
    assert result.response is None
    assert result.events == ()
    assert result.metrics is None
    assert result.error is None


def test_agent_execution_result_success_true_for_ready_state():
    assert _result(state=AgentState.READY).success is True


@pytest.mark.parametrize("state", [AgentState.FAILED, AgentState.CANCELLED])
def test_agent_execution_result_success_false_for_terminal_failure_states(state):
    assert _result(state=state).success is False


def test_agent_execution_result_is_frozen():
    result = _result()

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.agent_id = "changed"


# --- execution identity (M16.6) -----------------------------------------------------------


def test_agent_execution_result_carries_identity_fields_copied_from_a_context():
    shared = SharedExecutionContext(parent_execution_id="parent-1", causation_id="cause-1")

    result = _result(**shared.identity_fields())

    assert result.execution_id == shared.execution_id
    assert result.parent_execution_id == "parent-1"
    assert result.correlation_id == shared.correlation_id
    assert result.causation_id == "cause-1"


def test_agent_execution_result_identity_defaults_are_never_empty():
    result = _result()

    assert result.execution_id
    assert result.correlation_id
    assert result.parent_execution_id is None
    assert result.causation_id is None


def test_agent_execution_result_metadata_defaults_to_empty_read_only_mapping():
    result = _result()

    assert isinstance(result.metadata, MappingProxyType)
