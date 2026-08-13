from sqlalchemy.orm import Session

from app.models.pattern_record import PatternRecord
from app.repositories.base import BaseRepository


class PatternRecordRepository(BaseRepository[PatternRecord]):
    def __init__(self, db: Session):
        super().__init__(PatternRecord, db)

    def get_latest_by_type(self, organization_id: int, user_id: int, pattern_type: str) -> PatternRecord | None:
        return (
            self.db.query(PatternRecord)
            .filter(
                PatternRecord.organization_id == organization_id,
                PatternRecord.user_id == user_id,
                PatternRecord.pattern_type == pattern_type,
            )
            .order_by(PatternRecord.id.desc())
            .first()
        )

    def list_latest_per_type(self, organization_id: int, user_id: int) -> list[PatternRecord]:
        """The latest row per pattern_type - not filtered by status here
        (SqlPatternRepository.list_active does that filtering on the
        domain objects, after deserialization, keeping the "what counts
        as active" rule in one place rather than duplicated into a SQL
        WHERE clause too)."""
        all_rows = (
            self.db.query(PatternRecord)
            .filter(PatternRecord.organization_id == organization_id, PatternRecord.user_id == user_id)
            .order_by(PatternRecord.id.asc())
            .all()
        )
        latest_by_type: dict[str, PatternRecord] = {}
        for row in all_rows:
            latest_by_type[row.pattern_type] = row
        return list(latest_by_type.values())
