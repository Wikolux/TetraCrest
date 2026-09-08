from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.enums import ExecutionStatus
from app.models.execution_record import ExecutionRecord
from app.repositories.base import BaseRepository


class ExecutionRecordRepository(BaseRepository[ExecutionRecord]):
    """P7.16: the durable seam a future recovery/observability milestone
    would consume - this repository only creates, terminates, and reads;
    it does not itself recover or reconcile anything (list_non_terminal()
    exists purely to make non-terminal records discoverable later)."""

    def __init__(self, db: Session):
        super().__init__(ExecutionRecord, db)

    def create_started(
        self,
        *,
        execution_id: str,
        organization_id: int,
        operation: str,
        correlation_id: str | None = None,
        user_id: int | None = None,
        agent_id: str | None = None,
    ) -> ExecutionRecord:
        record = ExecutionRecord(
            execution_id=execution_id,
            correlation_id=correlation_id,
            organization_id=organization_id,
            user_id=user_id,
            agent_id=agent_id,
            operation=operation,
            status=ExecutionStatus.STARTED.value,
        )
        return self.create(record)

    def mark_succeeded(self, execution_id: str) -> ExecutionRecord:
        return self._mark_terminal(execution_id, ExecutionStatus.SUCCEEDED)

    def mark_failed(self, execution_id: str, *, error_summary: str | None = None) -> ExecutionRecord:
        return self._mark_terminal(execution_id, ExecutionStatus.FAILED, error_summary=error_summary)

    def _mark_terminal(self, execution_id: str, status: ExecutionStatus, *, error_summary: str | None = None) -> ExecutionRecord:
        record = self.db.query(ExecutionRecord).filter(ExecutionRecord.execution_id == execution_id).first()
        if record is None:
            raise ValueError(f"No ExecutionRecord found for execution_id={execution_id!r}")
        if record.status != ExecutionStatus.STARTED.value:
            # P7.16 §12: terminal outcomes are immutable - a STARTED record
            # transitions exactly once, to exactly one terminal status.
            raise ValueError(
                f"Cannot transition ExecutionRecord {execution_id!r} from terminal status "
                f"{record.status!r} to {status.value!r} - terminal outcomes are immutable"
            )
        record.status = status.value
        record.error_summary = error_summary
        record.finished_at = datetime.now(UTC)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_by_execution_id(self, execution_id: str, *, organization_id: int) -> ExecutionRecord | None:
        """Cross-tenant access and a missing row are intentionally
        indistinguishable (both return None) - mirrors
        BaseRepository.get_by_id_for_organization()'s own discipline
        exactly, applied to execution_id instead of the primary key."""
        record = self.db.query(ExecutionRecord).filter(ExecutionRecord.execution_id == execution_id).first()
        if record is None or record.organization_id != organization_id:
            return None
        return record

    def list_non_terminal(self, *, organization_id: int, user_id: int | None = None) -> list[ExecutionRecord]:
        query = self.db.query(ExecutionRecord).filter(
            ExecutionRecord.organization_id == organization_id,
            ExecutionRecord.status == ExecutionStatus.STARTED.value,
        )
        if user_id is not None:
            query = query.filter(ExecutionRecord.user_id == user_id)
        return query.all()
