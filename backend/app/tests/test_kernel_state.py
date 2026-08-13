from app.services.ai.kernel.state import ExecutionState


def test_execution_state_values():
    assert ExecutionState.PENDING == "pending"
    assert ExecutionState.VALIDATING == "validating"
    assert ExecutionState.QUEUED == "queued"
    assert ExecutionState.RUNNING == "running"
    assert ExecutionState.WAITING == "waiting"
    assert ExecutionState.RETRYING == "retrying"
    assert ExecutionState.CANCELLED == "cancelled"
    assert ExecutionState.FAILED == "failed"
    assert ExecutionState.COMPLETED == "completed"


def test_execution_state_members_are_all_distinct():
    values = [member.value for member in ExecutionState]
    assert len(values) == len(set(values))


def test_execution_state_behaves_as_plain_string():
    assert f"{ExecutionState.RUNNING}" == "running"
    assert isinstance(ExecutionState.RUNNING, str)
