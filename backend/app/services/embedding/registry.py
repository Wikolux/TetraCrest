from typing import Callable

from app.core.enums import EmbeddingProviderName
from app.services.ai.shared.provider_registry import GenericProviderRegistry
from app.services.embedding.base_provider import EmbeddingProvider, EmbeddingProviderError
from settings import Settings


class EmbeddingProviderRegistry(
    GenericProviderRegistry[EmbeddingProviderName, Callable[[Settings], EmbeddingProvider]]
):
    """Maps EmbeddingProviderName to a builder that constructs a concrete
    EmbeddingProvider from Settings.

    Built on GenericProviderRegistry (app.services.ai.shared.provider_registry)
    - the same base every AI Operating System registry uses - rather than a
    bare module-level dict, per M20.5's registry consolidation. Each entry
    is a builder callable (not a bare provider class) because construction
    here needs several distinct Settings fields per provider (api_key,
    model, max_retries, ...), not one uniform config object.
    """

    _registration_error = EmbeddingProviderError
