from datetime import date

from sqlalchemy.orm import Session

from app.models.day_event_record import DayEventRecord
from app.repositories.base import BaseRepository


class DayEventRecordRepository(BaseRepository[DayEventRecord]):
    def __init__(self, db: Session):
        super().__init__(DayEventRecord, db)

    def get_max_sequence(self, organization_id: int, user_id: int, day_date: date) -> int:
        record = (
            self.db.query(DayEventRecord)
            .filter(
                DayEventRecord.organization_id == organization_id,
                DayEventRecord.user_id == user_id,
                DayEventRecord.day_date == day_date,
            )
            .order_by(DayEventRecord.sequence.desc())
            .first()
        )
        return record.sequence if record else 0

    def list_for_day(self, organization_id: int, user_id: int, day_date: date) -> list[DayEventRecord]:
        return (
            self.db.query(DayEventRecord)
            .filter(
                DayEventRecord.organization_id == organization_id,
                DayEventRecord.user_id == user_id,
                DayEventRecord.day_date == day_date,
            )
            .order_by(DayEventRecord.sequence.asc())
            .all()
        )
