from sqlalchemy.orm import Session

from app.models.mission_record import MissionRecord
from app.repositories.base import BaseRepository


class MissionRecordRepository(BaseRepository[MissionRecord]):
    def __init__(self, db: Session):
        super().__init__(MissionRecord, db)

    def get_latest_by_mission_id(self, organization_id: int, user_id: int, mission_id: str) -> MissionRecord | None:
        return (
            self.db.query(MissionRecord)
            .filter(
                MissionRecord.organization_id == organization_id,
                MissionRecord.user_id == user_id,
                MissionRecord.mission_id == mission_id,
            )
            .order_by(MissionRecord.id.desc())
            .first()
        )

    def list_history(self, organization_id: int, user_id: int, mission_id: str) -> list[MissionRecord]:
        return (
            self.db.query(MissionRecord)
            .filter(
                MissionRecord.organization_id == organization_id,
                MissionRecord.user_id == user_id,
                MissionRecord.mission_id == mission_id,
            )
            .order_by(MissionRecord.id.asc())
            .all()
        )

    def list_latest_per_mission(self, organization_id: int, user_id: int) -> list[MissionRecord]:
        all_rows = (
            self.db.query(MissionRecord)
            .filter(MissionRecord.organization_id == organization_id, MissionRecord.user_id == user_id)
            .order_by(MissionRecord.id.asc())
            .all()
        )
        latest_by_mission: dict[str, MissionRecord] = {}
        for row in all_rows:
            latest_by_mission[row.mission_id] = row
        return list(latest_by_mission.values())
