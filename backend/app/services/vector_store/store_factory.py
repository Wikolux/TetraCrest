from app.core.enums import VectorStoreProviderName
from app.services.vector_store.base_store import VectorStore, VectorStoreError
from app.services.vector_store.null_store import NullVectorStore
from app.services.vector_store.pgvector_store import PgVectorStore
from settings import Settings, get_settings

_STORES = {
    VectorStoreProviderName.NULL: lambda settings: NullVectorStore(),
    VectorStoreProviderName.PGVECTOR: lambda settings: PgVectorStore(
        table_name=settings.vector_store_table, dimensions=settings.embedding_dimensions
    ),
}


def _validate(settings: Settings) -> None:
    if settings.vector_store_provider != VectorStoreProviderName.PGVECTOR:
        return
    if not settings.vector_store_table:
        raise VectorStoreError(
            "Vector store 'pgvector' requires vector_store_table to be configured"
        )
    if settings.embedding_dimensions <= 0:
        raise VectorStoreError(
            "Vector store 'pgvector' requires a positive embedding_dimensions, "
            f"got {settings.embedding_dimensions}"
        )


class VectorStoreFactory:
    """Resolves settings.vector_store_provider into a concrete VectorStore.

    Mirrors EmbeddingProviderFactory: the only place in the codebase that
    knows which store names exist and how each one is constructed. Adding a
    new backend (pgvector, Pinecone, Weaviate, Qdrant, Chroma, Redis) means
    adding one entry here, nothing else.

    Configuration is validated here, at creation time, rather than left to
    fail on the first save/get/delete call - an unsupported provider name
    or invalid dimensions should never construct a service successfully
    only to fail later on the request path.
    """

    @staticmethod
    def create(settings: Settings | None = None) -> VectorStore:
        settings = settings or get_settings()
        build = _STORES.get(settings.vector_store_provider)
        if build is None:
            raise VectorStoreError(
                f"Unsupported vector store provider: {settings.vector_store_provider}"
            )
        _validate(settings)
        return build(settings)
