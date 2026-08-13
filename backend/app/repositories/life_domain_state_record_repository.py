from sqlalchemy.orm import Session

from app.models.life_domain_state_record import LifeDomainStateRecord
from app.repositories.base import BaseRepository


class LifeDomainStateRecordRepository(BaseRepository[LifeDomainStateRecord]):
    def __init__(self, db: Session):
        super().__init__(LifeDomainStateRecord, db)

    def get_latest_by_domain(self, organization_id: int, user_id: int, domain: str) -> LifeDomainStateRecord | None:
        return (
            self.db.query(LifeDomainStateRecord)
            .filter(
                LifeDomainStateRecord.organization_id == organization_id,
                LifeDomainStateRecord.user_id == user_id,
                LifeDomainStateRecord.domain == domain,
            )
            .order_by(LifeDomainStateRecord.id.desc())
            .first()
        )

    def list_history(self, organization_id: int, user_id: int, domain: str) -> list[LifeDomainStateRecord]:
        return (
            self.db.query(LifeDomainStateRecord)
            .filter(
                LifeDomainStateRecord.organization_id == organization_id,
                LifeDomainStateRecord.user_id == user_id,
                LifeDomainStateRecord.domain == domain,
            )
            .order_by(LifeDomainStateRecord.id.asc())
            .all()
        )

    def list_latest_per_domain(self, organization_id: int, user_id: int) -> list[LifeDomainStateRecord]:
        all_rows = (
            self.db.query(LifeDomainStateRecord)
            .filter(LifeDomainStateRecord.organization_id == organization_id, LifeDomainStateRecord.user_id == user_id)
            .order_by(LifeDomainStateRecord.id.asc())
            .all()
        )
        latest_by_domain: dict[str, LifeDomainStateRecord] = {}
        for row in all_rows:
            latest_by_domain[row.domain] = row
        return list(latest_by_domain.values())
