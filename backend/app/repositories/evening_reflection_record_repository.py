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

    def list_by_date_range(
        self, organization_id: int, user_id: int, start: date, end: date
    ) -> list[EveningReflectionRecord]:
        """Every reflection in range, oldest first - added in P3 for
        multi-day pattern detection (pattern_evidence.py), mirroring
        DailyIntentRecordRepository.list_by_date_range's own precedent
        exactly."""
        return (
            self.db.query(EveningReflectionRecord)
            .filter(
                EveningReflectionRecord.organization_id == organization_id,
                EveningReflectionRecord.user_id == user_id,
                EveningReflectionRecord.reflection_date >= start,
                EveningReflectionRecord.reflection_date <= end,
            )
            .order_by(EveningReflectionRecord.reflection_date.asc(), EveningReflectionRecord.id.asc())
            .all()
        )
