import pytest

from app.services.ai.conversation.base_provider import ConversationProvider
from app.services.ai.conversation.provider_factory import ConversationProviderFactory
from app.services.ai.conversation.registry import ConversationProviderRegistry
from app.services.ai.providers.enums import ProviderName
from app.services.ai.shared.exceptions import AIProviderError
from app.services.ai.shared.provider_config import ConversationProviderConfig


class _FakeProvider(ConversationProvider):
    def __init__(self, config: ConversationProviderConfig | None = None):
        self.config = config or ConversationProviderConfig()

    def generate(self, prompt_package):
        raise NotImplementedError

    def health_check(self) -> bool:
        return True

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.OPENAI

    @property
    def model_name(self) -> str:
        return self.config.model or "fake-model"


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(ConversationProviderRegistry._providers)
    ConversationProviderRegistry._providers.clear()
    yield
    ConversationProviderRegistry._providers.clear()
    ConversationProviderRegistry._providers.update(original)


def test_factory_raises_ai_provider_error_when_no_provider_is_registered():
    with pytest.raises(AIProviderError, match="Unsupported conversation provider"):
        ConversationProviderFactory.create(ProviderName.OPENAI)


def test_factory_raises_ai_provider_error_for_any_unregistered_provider_name():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)

    with pytest.raises(AIProviderError, match="Unsupported conversation provider"):
        ConversationProviderFactory.create(ProviderName.ANTHROPIC)


def test_factory_constructs_the_registered_provider_class():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)

    provider = ConversationProviderFactory.create(ProviderName.OPENAI)

    assert isinstance(provider, _FakeProvider)
    assert isinstance(provider, ConversationProvider)


def test_factory_constructs_with_a_default_config_when_none_given():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)

    provider = ConversationProviderFactory.create(ProviderName.OPENAI)

    assert isinstance(provider.config, ConversationProviderConfig)
    assert provider.model_name == "fake-model"


def test_factory_passes_through_the_config_object():
    ConversationProviderRegistry.register(ProviderName.OPENAI, _FakeProvider)
    config = ConversationProviderConfig(model="custom-model", temperature=0.2)

    provider = ConversationProviderFactory.create(ProviderName.OPENAI, config=config)

    assert provider.config is config
    assert provider.model_name == "custom-model"


def test_factory_uses_the_registry_not_a_hardcoded_mapping():
    # registering a provider under a name the factory has never seen
    # before must work immediately, with no factory code change
    class _NewProvider(ConversationProvider):
        def __init__(self, config: ConversationProviderConfig | None = None):
            self.config = config or ConversationProviderConfig()

        def generate(self, prompt_package):
            raise NotImplementedError

        def health_check(self) -> bool:
            return True

        @property
        def provider_name(self) -> ProviderName:
            return ProviderName.MISTRAL

        @property
        def model_name(self) -> str:
            return "new-model"

    ConversationProviderRegistry.register(ProviderName.MISTRAL, _NewProvider)

    provider = ConversationProviderFactory.create(ProviderName.MISTRAL)

    assert isinstance(provider, _NewProvider)


def test_factory_reflects_registry_changes_made_after_a_prior_failed_lookup():
    with pytest.raises(AIProviderError):
        ConversationProviderFactory.create(ProviderName.GEMINI)

    ConversationProviderRegistry.register(ProviderName.GEMINI, _FakeProvider)

    # no factory change needed - it now succeeds simply because the
    # registry was updated
    provider = ConversationProviderFactory.create(ProviderName.GEMINI)
    assert isinstance(provider, _FakeProvider)
