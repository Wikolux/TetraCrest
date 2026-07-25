from app.models.memory_record import MemoryRecord
from app.repositories.base import BaseRepository
from sqlalchemy.orm import Session


class MemoryRecordRepository(BaseRepository[MemoryRecord]):
    def __init__(self, db: Session):
        super().__init__(MemoryRecord, db)

    def get_by_organization(self, organization_id: int, skip: int = 0, limit: int = 20):
        return (
            self.db.query(MemoryRecord)
            .filter(MemoryRecord.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
