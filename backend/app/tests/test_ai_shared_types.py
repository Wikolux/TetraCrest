import dataclasses

import pytest

from app.services.ai.shared.types import ProviderCapabilities, TokenUsage


def test_token_usage_construction():
    usage = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)

    assert usage.prompt_tokens == 10
    assert usage.completion_tokens == 20
    assert usage.total_tokens == 30


def test_token_usage_is_frozen():
    usage = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)

    with pytest.raises(dataclasses.FrozenInstanceError):
        usage.total_tokens = 999


def test_provider_capabilities_defaults_are_all_conservative():
    capabilities = ProviderCapabilities()

    assert capabilities.supports_streaming is False
    assert capabilities.supports_tools is False
    assert capabilities.supports_json_mode is False
    assert capabilities.supports_vision is False
    assert capabilities.supports_reasoning is False
    assert capabilities.max_context_tokens == 0
    assert capabilities.supports_images is False
    assert capabilities.supports_audio is False
    assert capabilities.supports_embeddings is False
    assert capabilities.supports_function_calling is False
    assert capabilities.supports_long_context is False


def test_provider_capabilities_construction_with_all_fields():
    capabilities = ProviderCapabilities(
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        supports_vision=True,
        supports_reasoning=True,
        max_context_tokens=128000,
        supports_images=True,
        supports_audio=True,
        supports_embeddings=True,
        supports_function_calling=True,
        supports_long_context=True,
    )

    assert capabilities.supports_streaming is True
    assert capabilities.supports_tools is True
    assert capabilities.supports_json_mode is True
    assert capabilities.supports_vision is True
    assert capabilities.supports_reasoning is True
    assert capabilities.max_context_tokens == 128000
    assert capabilities.supports_images is True
    assert capabilities.supports_audio is True
    assert capabilities.supports_embeddings is True
    assert capabilities.supports_function_calling is True
    assert capabilities.supports_long_context is True


def test_provider_capabilities_vision_and_images_are_independent_flags():
    # supports_vision (image understanding) and supports_images (image
    # generation) must be settable independently of each other
    vision_only = ProviderCapabilities(supports_vision=True, supports_images=False)
    images_only = ProviderCapabilities(supports_vision=False, supports_images=True)

    assert vision_only.supports_vision is True
    assert vision_only.supports_images is False
    assert images_only.supports_vision is False
    assert images_only.supports_images is True


def test_provider_capabilities_tools_and_function_calling_are_independent_flags():
    tools_only = ProviderCapabilities(supports_tools=True, supports_function_calling=False)
    function_calling_only = ProviderCapabilities(supports_tools=False, supports_function_calling=True)

    assert tools_only.supports_tools is True
    assert tools_only.supports_function_calling is False
    assert function_calling_only.supports_tools is False
    assert function_calling_only.supports_function_calling is True


def test_provider_capabilities_is_frozen():
    capabilities = ProviderCapabilities()

    with pytest.raises(dataclasses.FrozenInstanceError):
        capabilities.supports_streaming = True
