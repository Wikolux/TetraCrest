from app.services.embedding_service import EmbeddingService
from app.services.vector_store.base_store import VectorStore
from app.services.vector_store.store_factory import VectorStoreFactory
from app.services.vector_store.types import VectorMetadata


def _normalize_metadata(metadata: VectorMetadata | dict | None) -> dict | None:
    if isinstance(metadata, VectorMetadata):
        return metadata.to_dict()
    return metadata


class EmbeddingPersistenceService:
    """Coordinates embedding generation with vector storage.

    EmbeddingService only turns text into vectors; VectorStore only
    persists/retrieves vectors by id. This service is the only place that
    combines the two - callers that want "embed this text and store it"
    depend on this service, not on EmbeddingService and VectorStore
    separately.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ):
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStoreFactory.create()

    def generate_and_store(
        self, vector_id: str, text: str, metadata: VectorMetadata | dict | None = None
    ) -> list[float]:
        vector = self.embedding_service.generate_embedding(text)
        self.vector_store.save_vector(vector_id, vector, metadata=_normalize_metadata(metadata))
        return vector

    def generate_and_store_many(
        self,
        vector_ids: list[str],
        texts: list[str],
        metadata: list[VectorMetadata | dict | None] | None = None,
    ) -> list[list[float]]:
        """Embed and persist many texts in one batch, preserving order.

        Uses EmbeddingService.generate_embeddings (a single batched call to
        the provider) rather than looping generate_and_store, so a batch of
        N texts costs one provider round trip instead of N.
        """
        if len(vector_ids) != len(texts):
            raise ValueError("vector_ids and texts must be the same length")
        if metadata is not None and len(metadata) != len(texts):
            raise ValueError("metadata must be the same length as texts when provided")

        resolved_metadata = metadata or [None] * len(texts)
        vectors = self.embedding_service.generate_embeddings(texts)

        for vector_id, vector, item_metadata in zip(vector_ids, vectors, resolved_metadata):
            self.vector_store.save_vector(vector_id, vector, metadata=_normalize_metadata(item_metadata))

        return vectors

    def get_vector(self, vector_id: str) -> list[float] | None:
        return self.vector_store.get_vector(vector_id)

    def delete_vector(self, vector_id: str) -> bool:
        return self.vector_store.delete_vector(vector_id)

    def health_check(self) -> dict:
        """Return the health of both dependencies this service coordinates.

        {"embedding_provider": bool, "vector_store": bool} - the caller
        can see which half of the pipeline (if either) is unhealthy,
        instead of a single opaque bool.
        """
        return {
            "embedding_provider": self.embedding_service.provider.health_check(),
            "vector_store": self.vector_store.health_check(),
        }
