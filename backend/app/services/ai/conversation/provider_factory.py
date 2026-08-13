from app.services.ai.conversation.base_provider import ConversationProvider
from app.services.ai.conversation.registry import ConversationProviderRegistry
from app.services.ai.providers.enums import ProviderName
from app.services.ai.shared.base_factory import BaseProviderFactory
from app.services.ai.shared.provider_config import ConversationProviderConfig


class ConversationProviderFactory(BaseProviderFactory[ConversationProvider, ConversationProviderConfig]):
    """Resolves a ProviderName into a concrete ConversationProvider via
    ConversationProviderRegistry.

    Mirrors EmbeddingProviderFactory/VectorStoreFactory/
    MetricsRecorderFactory: the only place a provider identifier is
    turned into a live instance. It differs from those in one way -
    provider selection here has no settings.py integration yet (this
    milestone explicitly adds no settings/env vars), so create() takes
    provider_name explicitly rather than reading it from get_settings().
    Wiring this to configuration is future work, not this milestone's.

    Providers are now constructed from a ConversationProviderConfig
    object rather than raw **kwargs - a typed, immutable config a
    provider's __init__ receives as a single argument, instead of an
    open-ended keyword-argument surface. Shared "resolve or fail clearly"
    logic lives in BaseProviderFactory so a future VisionProviderFactory/
    ReasoningProviderFactory/etc. gets it for free rather than
    re-deriving it.

    No provider is registered yet, so every call raises AIProviderError
    today - that's expected and will keep being true until a real
    conversation provider registers itself.
    """

    @staticmethod
    def create(
        provider_name: ProviderName, config: ConversationProviderConfig | None = None
    ) -> ConversationProvider:
        provider_class = ConversationProviderRegistry.get(provider_name)
        return BaseProviderFactory.build(
            provider_class, provider_name, config or ConversationProviderConfig(), "conversation"
        )
