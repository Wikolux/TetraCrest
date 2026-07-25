from app.models.memory import Memory
from app.repositories.base import BaseRepository
from sqlalchemy.orm import Session


class MemoryRepository(BaseRepository[Memory]):
    def __init__(self, db: Session):
        super().__init__(Memory, db)

    def get_by_organization(self, organization_id: int, skip: int = 0, limit: int = 20):
        return (
            self.db.query(Memory)
            .filter(Memory.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
