from app.services.vector_store.base_store import VectorStore


class NullVectorStore(VectorStore):
    """No-op vector store used while no real vector database is wired up.

    Lets the application depend on a VectorStore today - construct one,
    hold a reference to it - without any vector database existing yet.
    Every method behaves safely: nothing is persisted, lookups always miss,
    deletes and health checks always succeed.
    """

    def save_vector(self, vector_id: str, vector: list[float], metadata: dict | None = None) -> None:
        return None

    def get_vector(self, vector_id: str) -> list[float] | None:
        return None

    def delete_vector(self, vector_id: str) -> bool:
        return True

    def health_check(self) -> bool:
        return True
