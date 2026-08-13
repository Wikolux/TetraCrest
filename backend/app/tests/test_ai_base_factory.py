from dataclasses import dataclass

import pytest

from app.services.ai.shared.base_factory import BaseProviderFactory
from app.services.ai.shared.exceptions import AIProviderError


@dataclass
class _FakeConfig:
    value: str = "default"


class _FakeProvider:
    def __init__(self, config: _FakeConfig):
        self.config = config


def test_build_raises_ai_provider_error_when_provider_class_is_none():
    with pytest.raises(AIProviderError, match="Unsupported vision provider"):
        BaseProviderFactory.build(None, "some-provider", _FakeConfig(), "vision")


def test_build_error_message_includes_the_capability_label_and_provider_name():
    with pytest.raises(AIProviderError, match="Unsupported reasoning provider: unknown-provider"):
        BaseProviderFactory.build(None, "unknown-provider", _FakeConfig(), "reasoning")


def test_build_constructs_the_provider_with_the_given_config():
    config = _FakeConfig(value="custom")

    provider = BaseProviderFactory.build(_FakeProvider, "fake", config, "conversation")

    assert isinstance(provider, _FakeProvider)
    assert provider.config is config


def test_build_is_reusable_across_different_capability_labels():
    # the same BaseProviderFactory.build call works identically regardless
    # of which future capability factory calls it - nothing here is
    # conversation-specific
    for label in ("conversation", "vision", "reasoning", "planning", "embedding", "tool"):
        provider = BaseProviderFactory.build(_FakeProvider, "fake", _FakeConfig(), label)
        assert isinstance(provider, _FakeProvider)
