from abc import ABC, abstractmethod

from app.services.vector_store.types import SearchResult


class VectorStoreError(Exception):
    """Raised when a vector store fails to save, fetch, delete, or report health.

    Callers catch this single type regardless of which concrete store is
    configured, so a storage backend outage never surfaces as an unhandled
    SDK/driver exception.
    """


class VectorStore(ABC):
    """Common contract for every vector storage backend.

    A concrete store persists and retrieves vectors however its backend
    requires (pgvector, Pinecone, Weaviate, Qdrant, Chroma, Redis, ...).
    Business services depend only on this interface, so adding a new
    backend never means changing a service or its callers.

    This class defines the contract only - no storage logic lives here.
    """

    @abstractmethod
    def save_vector(self, vector_id: str, vector: list[float], metadata: dict | None = None) -> None:
        """Persist a vector under vector_id, replacing any existing one."""
        raise NotImplementedError

    @abstractmethod
    def get_vector(self, vector_id: str) -> list[float] | None:
        """Return the vector stored under vector_id, or None if absent."""
        raise NotImplementedError

    @abstractmethod
    def delete_vector(self, vector_id: str) -> bool:
        """Delete the vector stored under vector_id. Return whether it existed."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        """Return whether the backend is reachable and able to serve requests."""
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query_vector: list[float],
        organization_id: int,
        resource_type: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Return the vectors nearest to query_vector for organization_id,
        optionally narrowed to resource_type, ordered nearest-first.

        This is a storage-level nearest-neighbor lookup, not a semantic
        search feature: no ranking/reranking policy, score thresholding, or
        multi-strategy retrieval lives here or anywhere in this milestone -
        that orchestration belongs to a future service that calls this.
        """
        raise NotImplementedError
