from sqlalchemy.orm import Session

from app.core.enums import ResourceType
from app.logging_utils import get_logger
from app.models.memory import Memory
from app.repositories.memory_repository import MemoryRepository
from app.services.embedding.base_provider import EmbeddingProviderError
from app.services.embedding_persistence_service import EmbeddingPersistenceService
from app.services.vector_store.base_store import VectorStoreError
from app.services.vector_store.types import VectorMetadata
from app.services.vector_store.vector_id import VectorId
from database import SessionLocal

logger = get_logger(__name__)


class AIMemoryService:
    def __init__(
        self,
        db: Session | None = None,
        embedding_persistence_service: EmbeddingPersistenceService | None = None,
    ):
        self.db = db or SessionLocal()
        self.repo = MemoryRepository(self.db)
        self.embedding_persistence_service = (
            embedding_persistence_service or self._build_embedding_persistence_service()
        )

    @staticmethod
    def _build_embedding_persistence_service() -> EmbeddingPersistenceService | None:
        """Construct the default EmbeddingPersistenceService, degrading to None
        if the embedding subsystem is misconfigured (e.g. no API key yet).

        Memory creation must work whether or not embeddings are configured -
        the same reasoning that makes NullVectorStore a safe default applies
        here: a missing/invalid embedding configuration should never stop
        the service itself from being usable.
        """
        try:
            return EmbeddingPersistenceService()
        except (EmbeddingProviderError, VectorStoreError):
            logger.error("embedding_persistence_service_unavailable", exc_info=True)
            return None

    def create_memory(
        self,
        organization_id: int,
        content: str,
        user_id: int | None = None,
        memory_type: str = "general",
        title: str | None = None,
    ) -> Memory:
        memory = Memory(
            organization_id=organization_id,
            user_id=user_id,
            memory_type=memory_type,
            title=title,
            content=content,
        )
        memory = self.repo.create(memory)
        self._persist_embedding(memory)
        return memory

    def _persist_embedding(self, memory: Memory) -> None:
        """Best-effort: the Memory row already exists by the time this runs,
        and any embedding failure here must never undo or block that.
        """
        if self.embedding_persistence_service is None:
            return
        try:
            self.embedding_persistence_service.generate_and_store(
                vector_id=VectorId.memory(memory.id),
                text=memory.content,
                metadata=VectorMetadata(
                    organization_id=memory.organization_id,
                    resource_type=ResourceType.MEMORY,
                    resource_id=memory.id,
                ),
            )
        except (EmbeddingProviderError, VectorStoreError) as exc:
            logger.error(
                "embedding_persistence_failed",
                extra={"resource_type": ResourceType.MEMORY, "resource_id": memory.id},
                exc_info=exc,
            )

    def get_memory(self, memory_id: int, organization_id: int) -> Memory | None:
        return self.repo.get_by_id_for_organization(memory_id, organization_id)

    def list_memories(self, organization_id: int, skip: int = 0, limit: int = 20):
        return self.repo.get_by_organization(organization_id, skip=skip, limit=limit)

    def update_memory(self, memory_id: int, organization_id: int, **fields) -> Memory | None:
        memory = self.repo.get_by_id_for_organization(memory_id, organization_id)
        if not memory:
            return None
        return self.repo.update(memory, **fields)

    def delete_memory(self, memory_id: int, organization_id: int) -> bool:
        memory = self.repo.get_by_id_for_organization(memory_id, organization_id)
        if not memory:
            return False
        self.repo.delete(memory)
        return True
