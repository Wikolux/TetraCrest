import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.agents.specialists.shared.response import SpecialistResponse
from app.services.ai.kernel.metrics import ExecutionMetrics


def test_defaults():
    response = SpecialistResponse(success=True)

    assert response.summary == ""
    assert response.findings == ()
    assert response.confidence == 0.0
    assert response.sources == ()
    assert response.recommendations == ()
    assert response.artifacts == ()
    assert response.reasoning_summary == ""
    assert response.execution_metrics is None
    assert response.error is None
    assert isinstance(response.execution_id, str) and response.execution_id
    assert isinstance(response.correlation_id, str) and response.correlation_id
    assert response.parent_execution_id is None
    assert response.causation_id is None


def test_two_responses_get_different_ids():
    assert SpecialistResponse(success=True).execution_id != SpecialistResponse(success=True).execution_id


def test_failure_construction():
    response = SpecialistResponse(success=False, error="boom")

    assert response.success is False
    assert response.error == "boom"


def test_tuple_fields_are_coerced_from_lists():
    response = SpecialistResponse(
        success=True,
        findings=["a", "b"],
        sources=["src1"],
        recommendations=["do this"],
        artifacts=["file.txt"],
    )

    assert response.findings == ("a", "b")
    assert response.sources == ("src1",)
    assert response.recommendations == ("do this",)
    assert response.artifacts == ("file.txt",)


def test_composes_execution_metrics_not_a_new_metrics_type():
    metrics = ExecutionMetrics(duration_ms=10.0, execution_id="exec-1")

    response = SpecialistResponse(success=True, execution_metrics=metrics)

    assert response.execution_metrics is metrics
    assert isinstance(response.execution_metrics, ExecutionMetrics)


def test_metadata_defaults_to_empty_read_only_mapping():
    assert isinstance(SpecialistResponse(success=True).metadata, MappingProxyType)


def test_metadata_cannot_be_mutated():
    response = SpecialistResponse(success=True, metadata={"a": 1})

    with pytest.raises(TypeError):
        response.metadata["a"] = 2


def test_is_frozen():
    response = SpecialistResponse(success=True)

    with pytest.raises(dataclasses.FrozenInstanceError):
        response.success = False


def test_identity_fields_can_be_explicitly_set():
    response = SpecialistResponse(
        success=True,
        execution_id="exec-1",
        parent_execution_id="parent-1",
        correlation_id="corr-1",
        causation_id="cause-1",
    )

    assert response.execution_id == "exec-1"
    assert response.parent_execution_id == "parent-1"
    assert response.correlation_id == "corr-1"
    assert response.causation_id == "cause-1"
