from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.repositories.memory_repository import MemoryRepository
from database import SessionLocal


class AIMemoryService:
    def __init__(self, db: Session | None = None):
        self.db = db or SessionLocal()
        self.repo = MemoryRepository(self.db)

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
        return self.repo.create(memory)

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
