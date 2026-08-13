import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.providers.enums import ProviderName
from app.services.ai.shared.response import AIResponseMetadata, FinishReason, ProviderResponse, UsageDetails


# --- FinishReason -----------------------------------------------------------------


def test_finish_reason_values():
    assert FinishReason.STOP == "stop"
    assert FinishReason.LENGTH == "length"
    assert FinishReason.CONTENT_FILTER == "content_filter"
    assert FinishReason.TOOL_CALL == "tool_call"
    assert FinishReason.ERROR == "error"
    assert FinishReason.CANCELLED == "cancelled"
    assert FinishReason.UNKNOWN == "unknown"


def test_finish_reason_members_are_all_distinct():
    values = [member.value for member in FinishReason]
    assert len(values) == len(set(values))


# --- UsageDetails -------------------------------------------------------------------


def test_usage_details_construction():
    usage = UsageDetails(prompt_tokens=10, completion_tokens=5, total_tokens=15)

    assert usage.prompt_tokens == 10
    assert usage.completion_tokens == 5
    assert usage.total_tokens == 15
    assert usage.cached_tokens is None
    assert usage.reasoning_tokens is None


def test_usage_details_construction_with_optional_fields():
    usage = UsageDetails(
        prompt_tokens=10, completion_tokens=5, total_tokens=15, cached_tokens=3, reasoning_tokens=2
    )

    assert usage.cached_tokens == 3
    assert usage.reasoning_tokens == 2


def test_usage_details_is_frozen():
    usage = UsageDetails(prompt_tokens=10, completion_tokens=5, total_tokens=15)

    with pytest.raises(dataclasses.FrozenInstanceError):
        usage.total_tokens = 999


# --- AIResponseMetadata --------------------------------------------------------------


def test_ai_response_metadata_construction():
    metadata = AIResponseMetadata(provider=ProviderName.OPENAI, model="gpt-test")

    assert metadata.provider == ProviderName.OPENAI
    assert metadata.model == "gpt-test"
    assert metadata.finish_reason == FinishReason.UNKNOWN
    assert metadata.latency_ms is None
    assert metadata.request_id is None


def test_ai_response_metadata_construction_with_all_fields():
    metadata = AIResponseMetadata(
        provider=ProviderName.ANTHROPIC,
        model="claude-test",
        finish_reason=FinishReason.STOP,
        latency_ms=123.4,
        request_id="req-1",
        metadata={"trace": "abc"},
    )

    assert metadata.finish_reason == FinishReason.STOP
    assert metadata.latency_ms == 123.4
    assert metadata.request_id == "req-1"
    assert metadata.metadata["trace"] == "abc"


def test_ai_response_metadata_metadata_is_read_only():
    metadata = AIResponseMetadata(provider=ProviderName.OPENAI, model="gpt-test", metadata={"a": 1})

    assert isinstance(metadata.metadata, MappingProxyType)
    with pytest.raises(TypeError):
        metadata.metadata["a"] = 2


def test_ai_response_metadata_is_frozen():
    metadata = AIResponseMetadata(provider=ProviderName.OPENAI, model="gpt-test")

    with pytest.raises(dataclasses.FrozenInstanceError):
        metadata.model = "changed"


# --- ProviderResponse -----------------------------------------------------------------


def test_provider_response_construction():
    metadata = AIResponseMetadata(provider=ProviderName.OPENAI, model="gpt-test")
    usage = UsageDetails(prompt_tokens=1, completion_tokens=1, total_tokens=2)

    response = ProviderResponse(metadata=metadata, usage=usage, raw_response={"id": "resp_1"})

    assert response.metadata is metadata
    assert response.usage is usage
    assert response.raw_response == {"id": "resp_1"}


def test_provider_response_usage_and_raw_response_default_to_none():
    response = ProviderResponse(metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="gpt-test"))

    assert response.usage is None
    assert response.raw_response is None


def test_provider_response_is_frozen():
    response = ProviderResponse(metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="gpt-test"))

    with pytest.raises(dataclasses.FrozenInstanceError):
        response.usage = None
