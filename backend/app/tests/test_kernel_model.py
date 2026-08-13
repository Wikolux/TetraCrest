import dataclasses

import pytest

from app.services.ai.kernel.model import ModelIdentity


def test_model_identity_requires_only_provider():
    model = ModelIdentity(provider="openai")

    assert model.provider == "openai"
    assert model.family is None
    assert model.model_name is None
    assert model.version is None
    assert model.context_window is None


def test_model_identity_capability_flags_default_to_false():
    model = ModelIdentity(provider="openai")

    assert model.supports_streaming is False
    assert model.supports_tools is False
    assert model.supports_images is False
    assert model.supports_audio is False
    assert model.supports_reasoning is False


def test_model_identity_construction_with_all_fields():
    model = ModelIdentity(
        provider="anthropic",
        family="claude",
        model_name="claude-test",
        version="5",
        context_window=200000,
        supports_streaming=True,
        supports_tools=True,
        supports_images=True,
        supports_audio=False,
        supports_reasoning=True,
    )

    assert model.provider == "anthropic"
    assert model.family == "claude"
    assert model.model_name == "claude-test"
    assert model.version == "5"
    assert model.context_window == 200000
    assert model.supports_streaming is True
    assert model.supports_tools is True
    assert model.supports_images is True
    assert model.supports_audio is False
    assert model.supports_reasoning is True


def test_model_identity_provider_is_a_plain_string_not_an_enum():
    model = ModelIdentity(provider="openai")

    assert type(model.provider) is str


def test_model_identity_is_frozen():
    model = ModelIdentity(provider="openai")

    with pytest.raises(dataclasses.FrozenInstanceError):
        model.provider = "anthropic"
