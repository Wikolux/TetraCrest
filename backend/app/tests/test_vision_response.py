import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.kernel.metrics import ExecutionMetrics
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.response import VisionResponse
from app.services.ai.vision.shared.types import DetectedObject, ExtractedTable, ExtractedText


def test_defaults():
    response = VisionResponse(success=True)

    assert response.extracted_text == ()
    assert response.tables == ()
    assert response.objects == ()
    assert response.structured_output is None
    assert response.confidence == 0.0
    assert response.provider is None
    assert response.model is None
    assert response.duration_ms == 0.0
    assert response.metrics is None
    assert response.error is None
    assert isinstance(response.execution_id, str) and response.execution_id
    assert isinstance(response.correlation_id, str) and response.correlation_id


def test_two_responses_get_different_ids():
    assert VisionResponse(success=True).execution_id != VisionResponse(success=True).execution_id


def test_failure_construction():
    response = VisionResponse(success=False, error="boom")

    assert response.success is False
    assert response.error == "boom"


def test_tuple_fields_are_coerced_from_lists():
    response = VisionResponse(
        success=True,
        extracted_text=[ExtractedText(content="hi")],
        tables=[ExtractedTable()],
        objects=[DetectedObject(label="cat")],
    )

    assert isinstance(response.extracted_text, tuple)
    assert isinstance(response.tables, tuple)
    assert isinstance(response.objects, tuple)


def test_composes_execution_metrics_not_a_new_metrics_type():
    metrics = ExecutionMetrics(duration_ms=10.0, execution_id="exec-1")

    response = VisionResponse(success=True, metrics=metrics)

    assert response.metrics is metrics
    assert isinstance(response.metrics, ExecutionMetrics)


def test_provider_and_model_fields():
    response = VisionResponse(success=True, provider=ProviderName.OPENAI, model="gpt-vision")

    assert response.provider == ProviderName.OPENAI
    assert response.model == "gpt-vision"


def test_structured_output_defaults_to_none_not_an_empty_mapping():
    assert VisionResponse(success=True).structured_output is None


def test_structured_output_is_coerced_to_a_read_only_mapping_when_given():
    response = VisionResponse(success=True, structured_output={"a": 1})

    assert isinstance(response.structured_output, MappingProxyType)
    with pytest.raises(TypeError):
        response.structured_output["a"] = 2


def test_metadata_defaults_to_empty_read_only_mapping():
    assert isinstance(VisionResponse(success=True).metadata, MappingProxyType)


def test_metadata_cannot_be_mutated():
    response = VisionResponse(success=True, metadata={"a": 1})

    with pytest.raises(TypeError):
        response.metadata["a"] = 2


def test_is_frozen():
    response = VisionResponse(success=True)

    with pytest.raises(dataclasses.FrozenInstanceError):
        response.success = False


def test_identity_fields_can_be_explicitly_set():
    response = VisionResponse(
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
