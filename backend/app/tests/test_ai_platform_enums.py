from app.services.ai.capabilities.enums import Capability
from app.services.ai.providers.enums import ProviderName


def test_provider_name_values():
    assert ProviderName.OPENAI == "openai"
    assert ProviderName.ANTHROPIC == "anthropic"
    assert ProviderName.GEMINI == "gemini"
    assert ProviderName.OLLAMA == "ollama"
    assert ProviderName.OPENROUTER == "openrouter"
    assert ProviderName.DEEPSEEK == "deepseek"
    assert ProviderName.QWEN == "qwen"
    assert ProviderName.MISTRAL == "mistral"
    assert ProviderName.GROK == "grok"
    assert ProviderName.UNKNOWN == "unknown"


def test_provider_name_members_are_all_distinct():
    values = [member.value for member in ProviderName]
    assert len(values) == len(set(values))


def test_provider_name_behaves_as_plain_string():
    assert f"{ProviderName.OPENAI}" == "openai"
    assert isinstance(ProviderName.OPENAI, str)


def test_capability_values():
    assert Capability.CONVERSATION == "conversation"
    assert Capability.EMBEDDING == "embedding"
    assert Capability.REASONING == "reasoning"
    assert Capability.VISION == "vision"
    assert Capability.SPEECH == "speech"
    assert Capability.IMAGE_GENERATION == "image_generation"
    assert Capability.RERANKING == "reranking"
    assert Capability.PLANNING == "planning"
    assert Capability.TOOL_CALLING == "tool_calling"


def test_capability_members_are_all_distinct():
    values = [member.value for member in Capability]
    assert len(values) == len(set(values))


def test_capability_behaves_as_plain_string():
    assert f"{Capability.CONVERSATION}" == "conversation"
    assert isinstance(Capability.CONVERSATION, str)
