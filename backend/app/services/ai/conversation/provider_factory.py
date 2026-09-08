from app.services.ai.conversation.base_provider import ConversationProvider
from app.services.ai.conversation.registry import ConversationProviderRegistry
from app.services.ai.providers.enums import ProviderName
from app.services.ai.shared.base_factory import BaseProviderFactory
from app.services.ai.shared.provider_config import ConversationProviderConfig
from app.services.conversation_providers.openai_provider import OpenAIConversationProvider

# P7.14: the platform's first real registration. Importing this module -
# which every real execution path already does, transitively, via
# RuntimeExecutor - is what makes OpenAIConversationProvider available in
# production without any separate composition/startup step to remember.
# The concrete provider itself lives outside app/services/ai/ entirely
# (app/services/conversation_providers/) - see its own module docstring
# for why - so this is the one place under app/services/ai/ that is
# allowed to know OpenAI exists at all. Every other ProviderName
# (ANTHROPIC, GEMINI, OLLAMA, ...) remains unregistered and unimplemented;
# adding one is exactly this one line, nothing in this factory or the
# registry itself needs to change.
ConversationProviderRegistry.register(ProviderName.OPENAI, OpenAIConversationProvider)


class ConversationProviderFactory(BaseProviderFactory[ConversationProvider, ConversationProviderConfig]):
    """Resolves a ProviderName into a concrete ConversationProvider via
    ConversationProviderRegistry.

    Mirrors EmbeddingProviderFactory/VectorStoreFactory/
    MetricsRecorderFactory: the only place a provider identifier is
    turned into a live instance. It differs from those in one way -
    provider selection here has no settings.py-driven DEFAULT yet (no
    "settings.conversation_provider" exists), so create() takes
    provider_name explicitly rather than reading a default from
    get_settings() - every RuntimeRequest already names its own provider
    explicitly (P7.14 §13), so no default-selection setting is needed for
    this milestone. Settings IS consulted for credentials/model defaults,
    inside the concrete provider itself (OpenAIConversationProvider), not
    here.

    Providers are constructed from a ConversationProviderConfig object
    rather than raw **kwargs - a typed, immutable config a provider's
    __init__ receives as a single argument, instead of an open-ended
    keyword-argument surface. Shared "resolve or fail clearly" logic
    lives in BaseProviderFactory so a future VisionProviderFactory/
    ReasoningProviderFactory/etc. gets it for free rather than
    re-deriving it.

    OpenAI is registered (see the module-level call above) as of P7.14 -
    the first real provider. Every other ProviderName remains
    unregistered and will raise AIProviderError until its own concrete
    provider is implemented and registered the same way.
    """

    @staticmethod
    def create(
        provider_name: ProviderName, config: ConversationProviderConfig | None = None
    ) -> ConversationProvider:
        provider_class = ConversationProviderRegistry.get(provider_name)
        return BaseProviderFactory.build(
            provider_class, provider_name, config or ConversationProviderConfig(), "conversation"
        )
