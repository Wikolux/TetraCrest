import dataclasses
from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from app.services.ai.agents.enums import AgentState
from app.services.ai.agents.executive.task_result import TaskResult
from app.services.ai.agents.types import AgentExecutionResult


def test_task_result_defaults():
    result = TaskResult(task_id="task-1", success=True)

    assert result.task_id == "task-1"
    assert result.success is True
    assert result.output is None
    assert result.agent_execution_result is None
    assert result.error is None


def test_task_result_failure_with_error():
    result = TaskResult(task_id="task-1", success=False, error="boom")

    assert result.success is False
    assert result.error == "boom"


def test_task_result_can_carry_arbitrary_output():
    result = TaskResult(task_id="task-1", success=True, output={"sections": []})

    assert result.output == {"sections": []}


def test_task_result_composes_an_agent_execution_result():
    now = datetime.now(UTC)
    agent_result = AgentExecutionResult(
        agent_id="agent-1", state=AgentState.READY, started_at=now, completed_at=now, duration_ms=1.0
    )

    result = TaskResult(task_id="task-1", success=True, agent_execution_result=agent_result)

    assert result.agent_execution_result is agent_result


def test_task_result_metadata_defaults_to_empty_read_only_mapping():
    assert isinstance(TaskResult(task_id="t", success=True).metadata, MappingProxyType)


def test_task_result_metadata_cannot_be_mutated():
    result = TaskResult(task_id="t", success=True, metadata={"a": 1})

    with pytest.raises(TypeError):
        result.metadata["a"] = 2


def test_task_result_is_frozen():
    result = TaskResult(task_id="t", success=True)

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.success = False
