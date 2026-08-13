from typing import Generic, TypeVar

from app.services.ai.shared.exceptions import AIProviderError

TProvider = TypeVar("TProvider")
TConfig = TypeVar("TConfig")


class BaseProviderFactory(Generic[TProvider, TConfig]):
    """Shared construction logic for every capability-specific provider factory.

    Today only ConversationProviderFactory exists; future capabilities
    (VisionProviderFactory, ReasoningProviderFactory, PlanningProviderFactory,
    EmbeddingProviderFactory, ToolProviderFactory, ... none implemented
    yet) each need exactly the same three steps - resolve a provider
    class from their own registry, fail clearly if nothing is registered,
    construct with a config object - which is exactly the logic this
    class holds. A capability-specific factory calls `build()` with its
    own registry lookup result rather than re-deriving this each time.

    Not meant to be used directly - it has no registry of its own and no
    capability opinion; a capability-specific factory (typed with its own
    TProvider/TConfig) is always the caller.
    """

    @staticmethod
    def build(provider_class: type[TProvider] | None, provider_name, config: TConfig, capability_label: str) -> TProvider:
        if provider_class is None:
            raise AIProviderError(f"Unsupported {capability_label} provider: {provider_name}")
        return provider_class(config)
