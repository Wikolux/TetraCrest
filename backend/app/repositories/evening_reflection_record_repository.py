from datetime import date

from sqlalchemy.orm import Session

from app.models.evening_reflection_record import EveningReflectionRecord
from app.repositories.base import BaseRepository


class EveningReflectionRecordRepository(BaseRepository[EveningReflectionRecord]):
    def __init__(self, db: Session):
        super().__init__(EveningReflectionRecord, db)

    def get_for_date(self, organization_id: int, user_id: int, reflection_date: date) -> EveningReflectionRecord | None:
        """One reflection per date is the expected shape (unlike
        DailyIntent, a reflection is written once, at day's end - see
        evening.py's own "never backfilled or edited" rule) - the latest
        by id if more than one somehow exists, never an error."""
        return (
            self.db.query(EveningReflectionRecord)
            .filter(
                EveningReflectionRecord.organization_id == organization_id,
                EveningReflectionRecord.user_id == user_id,
                EveningReflectionRecord.reflection_date == reflection_date,
            )
            .order_by(EveningReflectionRecord.id.desc())
            .first()
        )
