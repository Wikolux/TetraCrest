from app.core.enums import EmbeddingProviderName
from app.services.embedding.base_provider import EmbeddingProvider, EmbeddingProviderError
from app.services.embedding.openai_provider import OpenAIEmbeddingProvider
from app.services.embedding.registry import EmbeddingProviderRegistry
from settings import Settings, get_settings

EmbeddingProviderRegistry.register(
    EmbeddingProviderName.OPENAI,
    lambda settings: OpenAIEmbeddingProvider(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
        max_retries=settings.embedding_max_retries,
        base_delay_seconds=settings.embedding_retry_base_delay_seconds,
    ),
)

# Backward-compatible alias: a plain dict snapshot of the registry,
# preserved for existing direct imports (see app/tests/test_enums.py).
# Not a live view - registration happens once, at import time, above.
_PROVIDERS = EmbeddingProviderRegistry.all_registered()


def _validate(settings: Settings) -> None:
    if settings.embedding_provider == EmbeddingProviderName.OPENAI and not settings.openai_api_key:
        raise EmbeddingProviderError(
            "Embedding provider 'openai' requires OPENAI_API_KEY to be configured"
        )


class EmbeddingProviderFactory:
    """Resolves settings.embedding_provider into a concrete EmbeddingProvider.

    The only place in the codebase that knows which provider names exist
    and how each one is constructed. EmbeddingService (and anything else
    that needs a provider) asks this factory for one instead of holding its
    own registry - adding a new provider (Azure OpenAI, VoyageAI, Cohere, a
    local model) means registering it in EmbeddingProviderRegistry, nothing
    else.

    Configuration is validated here, at creation time, rather than left to
    fail on the first `embed()` call - a missing API key or unsupported
    provider name should never construct a service successfully only to
    fail later on the request path.
    """

    @staticmethod
    def create(settings: Settings | None = None) -> EmbeddingProvider:
        settings = settings or get_settings()
        build = EmbeddingProviderRegistry.get(settings.embedding_provider)
        if build is None:
            raise EmbeddingProviderError(
                f"Unsupported embedding provider: {settings.embedding_provider}"
            )
        _validate(settings)
        return build(settings)
