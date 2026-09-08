from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """The first real use of AuditLog (P7.15) - previously a real,
    already-migrated model with no repository wrapper anywhere in the
    codebase. Nothing here beyond the inherited BaseRepository.create():
    a durable audit record is one row, written once, never updated or
    queried back by this milestone - the same minimal shape every other
    BaseRepository[X] subclass in this codebase already follows."""

    def __init__(self, db: Session):
        super().__init__(AuditLog, db)
