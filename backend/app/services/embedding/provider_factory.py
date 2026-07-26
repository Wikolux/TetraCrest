from app.core.constants import EMBEDDING_PROVIDER_OPENAI
from app.services.embedding.base_provider import EmbeddingProvider, EmbeddingProviderError
from app.services.embedding.openai_provider import OpenAIEmbeddingProvider
from settings import Settings, get_settings

_PROVIDERS = {
    EMBEDDING_PROVIDER_OPENAI: lambda settings: OpenAIEmbeddingProvider(
        api_key=settings.openai_api_key, model=settings.embedding_model
    ),
}


def _validate(settings: Settings) -> None:
    if settings.embedding_provider == EMBEDDING_PROVIDER_OPENAI and not settings.openai_api_key:
        raise EmbeddingProviderError(
            "Embedding provider 'openai' requires OPENAI_API_KEY to be configured"
        )


class EmbeddingProviderFactory:
    """Resolves settings.embedding_provider into a concrete EmbeddingProvider.

    The only place in the codebase that knows which provider names exist
    and how each one is constructed. EmbeddingService (and anything else
    that needs a provider) asks this factory for one instead of holding its
    own registry - adding a new provider (Azure OpenAI, VoyageAI, Cohere, a
    local model) means adding one entry here, nothing else.

    Configuration is validated here, at creation time, rather than left to
    fail on the first `embed()` call - a missing API key or unsupported
    provider name should never construct a service successfully only to
    fail later on the request path.
    """

    @staticmethod
    def create(settings: Settings | None = None) -> EmbeddingProvider:
        settings = settings or get_settings()
        build = _PROVIDERS.get(settings.embedding_provider)
        if build is None:
            raise EmbeddingProviderError(
                f"Unsupported embedding provider: {settings.embedding_provider}"
            )
        _validate(settings)
        return build(settings)
