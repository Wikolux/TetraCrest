import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.shared.provider_config import BaseProviderConfig, ConversationProviderConfig


# --- BaseProviderConfig ------------------------------------------------------------


def test_base_provider_config_defaults():
    config = BaseProviderConfig()

    assert config.api_key is None
    assert config.base_url is None
    assert config.timeout is None
    assert config.max_retries == 3
    assert dict(config.headers) == {}
    assert dict(config.metadata) == {}


def test_base_provider_config_construction_with_all_fields():
    config = BaseProviderConfig(
        api_key="secret",
        base_url="https://api.example.com",
        timeout=30.0,
        max_retries=5,
        headers={"X-Custom": "1"},
        metadata={"env": "prod"},
    )

    assert config.api_key == "secret"
    assert config.base_url == "https://api.example.com"
    assert config.timeout == 30.0
    assert config.max_retries == 5
    assert config.headers["X-Custom"] == "1"
    assert config.metadata["env"] == "prod"


def test_base_provider_config_headers_and_metadata_are_read_only():
    config = BaseProviderConfig(headers={"a": "1"}, metadata={"b": "2"})

    assert isinstance(config.headers, MappingProxyType)
    assert isinstance(config.metadata, MappingProxyType)
    with pytest.raises(TypeError):
        config.headers["a"] = "2"
    with pytest.raises(TypeError):
        config.metadata["b"] = "3"


def test_base_provider_config_is_frozen():
    config = BaseProviderConfig()

    with pytest.raises(dataclasses.FrozenInstanceError):
        config.api_key = "changed"


def test_base_provider_config_has_no_vendor_specific_fields():
    field_names = {f.name for f in dataclasses.fields(BaseProviderConfig)}
    assert not (field_names & {"organization", "azure_deployment", "project_id"})


# --- ConversationProviderConfig -----------------------------------------------------


def test_conversation_provider_config_inherits_base_fields():
    config = ConversationProviderConfig(api_key="secret", timeout=10.0)

    assert config.api_key == "secret"
    assert config.timeout == 10.0
    assert config.max_retries == 3  # inherited default


def test_conversation_provider_config_defaults():
    config = ConversationProviderConfig()

    assert config.model is None
    assert config.temperature is None
    assert config.top_p is None
    assert config.max_tokens is None
    assert config.organization is None


def test_conversation_provider_config_construction_with_all_fields():
    config = ConversationProviderConfig(
        api_key="secret",
        model="gpt-test",
        temperature=0.7,
        top_p=0.9,
        max_tokens=1024,
        organization="org-123",
    )

    assert config.model == "gpt-test"
    assert config.temperature == 0.7
    assert config.top_p == 0.9
    assert config.max_tokens == 1024
    assert config.organization == "org-123"


def test_conversation_provider_config_is_a_base_provider_config():
    assert isinstance(ConversationProviderConfig(), BaseProviderConfig)


def test_conversation_provider_config_is_frozen():
    config = ConversationProviderConfig(model="gpt-test")

    with pytest.raises(dataclasses.FrozenInstanceError):
        config.model = "changed"


def test_conversation_provider_config_headers_and_metadata_still_coerced():
    config = ConversationProviderConfig(headers={"a": "1"})

    assert isinstance(config.headers, MappingProxyType)
