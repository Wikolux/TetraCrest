import dataclasses

import pytest

from app.services.ai.conversation.types import ConversationResponse, ConversationStreamChunk
from app.services.ai.providers.enums import ProviderName
from app.services.ai.shared.response import AIResponseMetadata, FinishReason, ProviderResponse, UsageDetails


def _usage():
    return UsageDetails(prompt_tokens=10, completion_tokens=5, total_tokens=15)


def _provider_response(raw_response=None, finish_reason=FinishReason.STOP, usage=None):
    return ProviderResponse(
        metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="gpt-test", finish_reason=finish_reason),
        usage=usage if usage is not None else _usage(),
        raw_response=raw_response,
    )


def test_conversation_response_construction():
    response = ConversationResponse(text="hello there", response=_provider_response())

    assert response.text == "hello there"
    assert response.provider == ProviderName.OPENAI
    assert response.model == "gpt-test"
    assert response.finish_reason == FinishReason.STOP
    assert response.usage == _usage()


def test_conversation_response_raw_response_defaults_to_none():
    response = ConversationResponse(text="hi", response=_provider_response())

    assert response.raw_response is None


def test_conversation_response_accepts_optional_raw_response():
    raw = {"id": "resp_123"}

    response = ConversationResponse(text="hi", response=_provider_response(raw_response=raw))

    assert response.raw_response is raw


def test_conversation_response_delegates_to_the_composed_provider_response():
    provider_response = _provider_response()

    response = ConversationResponse(text="hi", response=provider_response)

    assert response.response is provider_response


def test_conversation_response_is_frozen():
    response = ConversationResponse(text="hi", response=_provider_response())

    with pytest.raises(dataclasses.FrozenInstanceError):
        response.text = "changed"


def test_conversation_response_provider_property_cannot_be_reassigned():
    response = ConversationResponse(text="hi", response=_provider_response())

    with pytest.raises(dataclasses.FrozenInstanceError):
        response.provider = ProviderName.ANTHROPIC


# --- ConversationStreamChunk ----------------------------------------------------


def test_conversation_stream_chunk_construction():
    chunk = ConversationStreamChunk(delta="Hello", provider=ProviderName.OPENAI, model="gpt-test")

    assert chunk.delta == "Hello"
    assert chunk.provider == ProviderName.OPENAI
    assert chunk.model == "gpt-test"
    assert chunk.finish_reason is None
    assert chunk.usage is None


def test_conversation_stream_chunk_can_carry_a_terminal_finish_reason_and_usage():
    usage = _usage()

    chunk = ConversationStreamChunk(
        delta="",
        provider=ProviderName.OPENAI,
        model="gpt-test",
        finish_reason=FinishReason.STOP,
        usage=usage,
    )

    assert chunk.finish_reason == FinishReason.STOP
    assert chunk.usage == usage


def test_conversation_stream_chunk_is_frozen():
    chunk = ConversationStreamChunk(delta="Hello", provider=ProviderName.OPENAI, model="gpt-test")

    with pytest.raises(dataclasses.FrozenInstanceError):
        chunk.delta = "changed"
