from app.services.ai.kernel.scheduling import ExecutionMode


def test_execution_mode_values():
    assert ExecutionMode.IMMEDIATE == "immediate"
    assert ExecutionMode.QUEUED == "queued"
    assert ExecutionMode.SCHEDULED == "scheduled"
    assert ExecutionMode.PARALLEL == "parallel"
    assert ExecutionMode.DISTRIBUTED == "distributed"


def test_execution_mode_members_are_all_distinct():
    values = [member.value for member in ExecutionMode]
    assert len(values) == len(set(values))


def test_execution_mode_behaves_as_plain_string():
    assert f"{ExecutionMode.PARALLEL}" == "parallel"
    assert isinstance(ExecutionMode.PARALLEL, str)
