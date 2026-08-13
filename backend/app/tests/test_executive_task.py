import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.agents.executive.task import Task, TaskStatus


def test_task_defaults():
    task = Task(title="Retrieve memory", execution_id="exec-1")

    assert task.title == "Retrieve memory"
    assert task.execution_id == "exec-1"
    assert task.parent_task_id is None
    assert task.description == ""
    assert task.status == TaskStatus.PENDING
    assert task.priority == 0
    assert task.assigned_agent is None
    assert task.dependencies == ()
    assert isinstance(task.task_id, str) and task.task_id


def test_two_tasks_get_different_ids():
    first = Task(title="a", execution_id="exec-1")
    second = Task(title="a", execution_id="exec-1")

    assert first.task_id != second.task_id


def test_dependencies_is_coerced_to_a_tuple():
    task = Task(title="a", execution_id="exec-1", dependencies=["dep-1", "dep-2"])

    assert task.dependencies == ("dep-1", "dep-2")


def test_metadata_defaults_to_empty_read_only_mapping():
    task = Task(title="a", execution_id="exec-1")

    assert isinstance(task.metadata, MappingProxyType)


def test_metadata_cannot_be_mutated():
    task = Task(title="a", execution_id="exec-1", metadata={"kind": "retrieve_memory"})

    with pytest.raises(TypeError):
        task.metadata["kind"] = "other"


def test_task_is_frozen():
    task = Task(title="a", execution_id="exec-1")

    with pytest.raises(dataclasses.FrozenInstanceError):
        task.status = TaskStatus.RUNNING


def test_with_status_returns_a_new_task_and_leaves_the_original_unchanged():
    task = Task(title="a", execution_id="exec-1")

    updated = task.with_status(TaskStatus.RUNNING)

    assert updated.status == TaskStatus.RUNNING
    assert task.status == TaskStatus.PENDING
    assert updated.task_id == task.task_id


def test_with_assigned_agent_sets_status_to_assigned():
    task = Task(title="a", execution_id="exec-1")

    updated = task.with_assigned_agent("research-agent")

    assert updated.assigned_agent == "research-agent"
    assert updated.status == TaskStatus.ASSIGNED
    assert task.assigned_agent is None
