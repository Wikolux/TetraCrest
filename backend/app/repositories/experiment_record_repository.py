from sqlalchemy.orm import Session

from app.models.experiment_record import ExperimentRecord
from app.repositories.base import BaseRepository


class ExperimentRecordRepository(BaseRepository[ExperimentRecord]):
    def __init__(self, db: Session):
        super().__init__(ExperimentRecord, db)

    def get_latest_by_experiment_id(self, organization_id: int, user_id: int, experiment_id: str) -> ExperimentRecord | None:
        return (
            self.db.query(ExperimentRecord)
            .filter(
                ExperimentRecord.organization_id == organization_id,
                ExperimentRecord.user_id == user_id,
                ExperimentRecord.experiment_id == experiment_id,
            )
            .order_by(ExperimentRecord.id.desc())
            .first()
        )

    def list_history(self, organization_id: int, user_id: int, experiment_id: str) -> list[ExperimentRecord]:
        return (
            self.db.query(ExperimentRecord)
            .filter(
                ExperimentRecord.organization_id == organization_id,
                ExperimentRecord.user_id == user_id,
                ExperimentRecord.experiment_id == experiment_id,
            )
            .order_by(ExperimentRecord.id.asc())
            .all()
        )

    def list_latest_per_experiment(self, organization_id: int, user_id: int) -> list[ExperimentRecord]:
        """The latest row per experiment_id - not filtered by status here
        (SqlExperimentRepository.list_active/list_ready_for_review do
        that filtering on the domain objects, after deserialization,
        mirroring PatternRecordRepository's own list_latest_per_type)."""
        all_rows = (
            self.db.query(ExperimentRecord)
            .filter(ExperimentRecord.organization_id == organization_id, ExperimentRecord.user_id == user_id)
            .order_by(ExperimentRecord.id.asc())
            .all()
        )
        latest_by_experiment: dict[str, ExperimentRecord] = {}
        for row in all_rows:
            latest_by_experiment[row.experiment_id] = row
        return list(latest_by_experiment.values())
