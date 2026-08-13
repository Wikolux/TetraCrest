import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.agents.specialists.shared.task import SpecialistTask, SpecialistTaskType


def test_every_documented_task_type_exists():
    assert {member.value for member in SpecialistTaskType} == {
        "research",
        "analysis",
        "summarization",
        "comparison",
        "verification",
        "investigation",
        "unknown",
    }


def test_defaults():
    task = SpecialistTask(task_type=SpecialistTaskType.RESEARCH, title="Gather info")

    assert task.description == ""
    assert isinstance(task.task_id, str) and task.task_id


def test_two_tasks_get_different_ids():
    first = SpecialistTask(task_type=SpecialistTaskType.RESEARCH, title="a")
    second = SpecialistTask(task_type=SpecialistTaskType.RESEARCH, title="a")

    assert first.task_id != second.task_id


def test_metadata_defaults_to_empty_read_only_mapping():
    assert isinstance(SpecialistTask(task_type=SpecialistTaskType.RESEARCH, title="a").metadata, MappingProxyType)


def test_metadata_cannot_be_mutated():
    task = SpecialistTask(task_type=SpecialistTaskType.RESEARCH, title="a", metadata={"k": "v"})

    with pytest.raises(TypeError):
        task.metadata["k"] = "changed"


def test_is_frozen():
    task = SpecialistTask(task_type=SpecialistTaskType.RESEARCH, title="a")

    with pytest.raises(dataclasses.FrozenInstanceError):
        task.title = "changed"


def test_is_hashable_and_usable_in_a_set():
    task = SpecialistTask(task_type=SpecialistTaskType.RESEARCH, title="a")

    assert isinstance(hash(task), int)
    assert task in {task}
