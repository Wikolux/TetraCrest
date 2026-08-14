from sqlalchemy.orm import Session

from app.models.adaptation_record import AdaptationRecord
from app.repositories.base import BaseRepository


class AdaptationRecordRepository(BaseRepository[AdaptationRecord]):
    def __init__(self, db: Session):
        super().__init__(AdaptationRecord, db)

    def get_latest_by_adaptation_id(self, organization_id: int, user_id: int, adaptation_id: str) -> AdaptationRecord | None:
        return (
            self.db.query(AdaptationRecord)
            .filter(
                AdaptationRecord.organization_id == organization_id,
                AdaptationRecord.user_id == user_id,
                AdaptationRecord.adaptation_id == adaptation_id,
            )
            .order_by(AdaptationRecord.id.desc())
            .first()
        )

    def list_history(self, organization_id: int, user_id: int, adaptation_id: str) -> list[AdaptationRecord]:
        return (
            self.db.query(AdaptationRecord)
            .filter(
                AdaptationRecord.organization_id == organization_id,
                AdaptationRecord.user_id == user_id,
                AdaptationRecord.adaptation_id == adaptation_id,
            )
            .order_by(AdaptationRecord.id.asc())
            .all()
        )

    def list_latest_per_adaptation(self, organization_id: int, user_id: int) -> list[AdaptationRecord]:
        all_rows = (
            self.db.query(AdaptationRecord)
            .filter(AdaptationRecord.organization_id == organization_id, AdaptationRecord.user_id == user_id)
            .order_by(AdaptationRecord.id.asc())
            .all()
        )
        latest_by_adaptation: dict[str, AdaptationRecord] = {}
        for row in all_rows:
            latest_by_adaptation[row.adaptation_id] = row
        return list(latest_by_adaptation.values())
