from typing import Callable

from app.core.enums import VectorStoreProviderName
from app.services.ai.shared.provider_registry import GenericProviderRegistry
from app.services.vector_store.base_store import VectorStore, VectorStoreError
from settings import Settings


class VectorStoreRegistry(GenericProviderRegistry[VectorStoreProviderName, Callable[[Settings], VectorStore]]):
    """Maps VectorStoreProviderName to a builder that constructs a concrete
    VectorStore from Settings.

    Built on GenericProviderRegistry (app.services.ai.shared.provider_registry)
    - the same base every AI Operating System registry uses - rather than a
    bare module-level dict, per M20.5's registry consolidation. Mirrors
    app.services.embedding.registry.EmbeddingProviderRegistry exactly.
    """

    _registration_error = VectorStoreError
