import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.kernel.metrics import ExecutionMetrics
from app.services.ai.tools.result import ToolResult


def test_defaults():
    result = ToolResult(success=True)

    assert result.output is None
    assert result.structured_output is None
    assert result.artifacts == ()
    assert result.metrics is None
    assert result.execution_time_ms == 0.0
    assert result.error is None
    assert isinstance(result.execution_id, str) and result.execution_id
    assert isinstance(result.correlation_id, str) and result.correlation_id
    assert result.parent_execution_id is None
    assert result.causation_id is None


def test_two_results_get_different_ids():
    assert ToolResult(success=True).execution_id != ToolResult(success=True).execution_id


def test_failure_construction():
    result = ToolResult(success=False, error="boom")

    assert result.success is False
    assert result.error == "boom"


def test_artifacts_is_coerced_to_a_tuple():
    result = ToolResult(success=True, artifacts=["a.txt", "b.txt"])

    assert result.artifacts == ("a.txt", "b.txt")


def test_composes_execution_metrics_not_a_new_metrics_type():
    metrics = ExecutionMetrics(duration_ms=42.0, execution_id="exec-1")

    result = ToolResult(success=True, metrics=metrics)

    assert result.metrics is metrics
    assert isinstance(result.metrics, ExecutionMetrics)


def test_structured_output_defaults_to_none_not_an_empty_mapping():
    assert ToolResult(success=True).structured_output is None


def test_structured_output_is_coerced_to_a_read_only_mapping_when_given():
    result = ToolResult(success=True, structured_output={"a": 1})

    assert isinstance(result.structured_output, MappingProxyType)
    with pytest.raises(TypeError):
        result.structured_output["a"] = 2


def test_metadata_defaults_to_empty_read_only_mapping():
    assert isinstance(ToolResult(success=True).metadata, MappingProxyType)


def test_metadata_cannot_be_mutated():
    result = ToolResult(success=True, metadata={"a": 1})

    with pytest.raises(TypeError):
        result.metadata["a"] = 2


def test_is_frozen():
    result = ToolResult(success=True)

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.success = False


def test_identity_fields_can_be_explicitly_set():
    result = ToolResult(
        success=True,
        execution_id="exec-1",
        parent_execution_id="parent-1",
        correlation_id="corr-1",
        causation_id="cause-1",
    )

    assert result.execution_id == "exec-1"
    assert result.parent_execution_id == "parent-1"
    assert result.correlation_id == "corr-1"
    assert result.causation_id == "cause-1"
