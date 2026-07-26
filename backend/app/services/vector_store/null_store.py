from app.services.vector_store.base_store import VectorStore
from app.services.vector_store.types import SearchResult


class NullVectorStore(VectorStore):
    """No-op vector store used while no real vector database is wired up.

    Lets the application depend on a VectorStore today - construct one,
    hold a reference to it - without any vector database existing yet.
    Every method behaves safely: nothing is persisted, lookups always miss,
    deletes and health checks always succeed, and search always returns no
    matches (there's nothing to search).
    """

    def save_vector(self, vector_id: str, vector: list[float], metadata: dict | None = None) -> None:
        return None

    def get_vector(self, vector_id: str) -> list[float] | None:
        return None

    def delete_vector(self, vector_id: str) -> bool:
        return True

    def health_check(self) -> bool:
        return True

    def search(
        self,
        query_vector: list[float],
        organization_id: int,
        resource_type: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        return []
