from datetime import date

from sqlalchemy.orm import Session

from app.models.daily_intent_record import DailyIntentRecord
from app.repositories.base import BaseRepository


class DailyIntentRecordRepository(BaseRepository[DailyIntentRecord]):
    def __init__(self, db: Session):
        super().__init__(DailyIntentRecord, db)

    def get_latest_for_date(self, organization_id: int, user_id: int, intent_date: date) -> DailyIntentRecord | None:
        """The most recent version for one exact date - id is
        monotonically increasing and every save() is a new row, so the
        highest id is always the latest version."""
        return (
            self.db.query(DailyIntentRecord)
            .filter(
                DailyIntentRecord.organization_id == organization_id,
                DailyIntentRecord.user_id == user_id,
                DailyIntentRecord.intent_date == intent_date,
            )
            .order_by(DailyIntentRecord.id.desc())
            .first()
        )

    def get_latest_before(self, organization_id: int, user_id: int, before: date) -> DailyIntentRecord | None:
        """The most recent record strictly before `before`, regardless of
        how many days were skipped in between."""
        return (
            self.db.query(DailyIntentRecord)
            .filter(
                DailyIntentRecord.organization_id == organization_id,
                DailyIntentRecord.user_id == user_id,
                DailyIntentRecord.intent_date < before,
            )
            .order_by(DailyIntentRecord.intent_date.desc(), DailyIntentRecord.id.desc())
            .first()
        )

    def list_by_date_range(
        self, organization_id: int, user_id: int, start: date, end: date
    ) -> list[DailyIntentRecord]:
        """Every version in range, oldest first - a caller wanting only
        the latest-per-date filters client-side (versions are rare enough
        per day that this is simpler than a window-function query, and
        matches InMemoryDailyIntentRepository's own O(n) precedent)."""
        return (
            self.db.query(DailyIntentRecord)
            .filter(
                DailyIntentRecord.organization_id == organization_id,
                DailyIntentRecord.user_id == user_id,
                DailyIntentRecord.intent_date >= start,
                DailyIntentRecord.intent_date <= end,
            )
            .order_by(DailyIntentRecord.intent_date.asc(), DailyIntentRecord.id.asc())
            .all()
        )
