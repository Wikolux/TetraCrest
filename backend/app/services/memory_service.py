from sqlalchemy.orm import Session

from app.models.memory_record import MemoryRecord
from app.repositories.memory_record_repository import MemoryRecordRepository
from database import SessionLocal


class MemoryService:
    def __init__(self, db: Session | None = None):
        self.db = db or SessionLocal()
        self.repo = MemoryRecordRepository(self.db)

    def create(self, key: str, value: str, organization_id: int, memory_type: str = "note") -> MemoryRecord:
        record = MemoryRecord(key=key, value=value, organization_id=organization_id, memory_type=memory_type)
        return self.repo.create(record)

    def list_for_organization(self, organization_id: int, skip: int = 0, limit: int = 20):
        return self.repo.get_by_organization(organization_id, skip=skip, limit=limit)

    def update(self, record_id: int, organization_id: int, **fields) -> MemoryRecord | None:
        record = self.repo.get_by_id_for_organization(record_id, organization_id)
        if not record:
            return None
        return self.repo.update(record, **fields)

    def delete(self, record_id: int, organization_id: int) -> bool:
        record = self.repo.get_by_id_for_organization(record_id, organization_id)
        if not record:
            return False
        self.repo.delete(record)
        return True
