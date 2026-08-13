import dataclasses

import pytest

from app.services.ai.shared.provider_metadata import ProviderMetadata


def test_provider_metadata_requires_only_provider_name():
    metadata = ProviderMetadata(provider_name="openai")

    assert metadata.provider_name == "openai"
    assert metadata.vendor is None
    assert metadata.homepage is None
    assert metadata.license is None
    assert metadata.context_window is None
    assert metadata.max_output_tokens is None


def test_provider_metadata_defaults_supports_cloud_true_supports_local_false():
    metadata = ProviderMetadata(provider_name="openai")

    assert metadata.supports_cloud is True
    assert metadata.supports_local is False


def test_provider_metadata_construction_with_all_fields():
    metadata = ProviderMetadata(
        provider_name="ollama",
        vendor="Ollama",
        homepage="https://ollama.com",
        license="MIT",
        supports_local=True,
        supports_cloud=False,
        context_window=8192,
        max_output_tokens=2048,
    )

    assert metadata.vendor == "Ollama"
    assert metadata.homepage == "https://ollama.com"
    assert metadata.license == "MIT"
    assert metadata.supports_local is True
    assert metadata.supports_cloud is False
    assert metadata.context_window == 8192
    assert metadata.max_output_tokens == 2048


def test_provider_metadata_is_frozen():
    metadata = ProviderMetadata(provider_name="openai")

    with pytest.raises(dataclasses.FrozenInstanceError):
        metadata.provider_name = "anthropic"
