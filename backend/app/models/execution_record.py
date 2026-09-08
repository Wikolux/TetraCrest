from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from database import Base


class ExecutionRecord(Base):
    """P7.16: durable, pre-commit operational execution state - the
    smallest possible answer to "was this operation never attempted,
    completed, failed, or left incomplete when execution stopped?"

    Deliberately a single, mutable current-state row per execution
    (unique execution_id, updated in place to a terminal status) - a
    genuinely different persistence shape from every other Personal-OS
    style "versioned entity" (Adaptation/Experiment/Pattern all append a
    new row per transition and never update). This table answers "what
    is happening right now," not "what is the full history" - that
    remains AuditLog's own, separate responsibility (see
    app/models/audit_log.py and app/api/v1/routes/research.py's own
    module docstring for the exact division of labor).

    A STARTED row is written and committed BEFORE any external
    operational call is attempted - never proof an external system
    received anything, only proof Tetra itself durably began the
    workflow. error_summary, when set, is always an already-normalized,
    already-safe error string (e.g. RuntimeResponse.error/
    SpecialistResponse.error - both proven elsewhere never to leak
    secrets) - never a raw exception/traceback.
    """

    __tablename__ = "execution_records"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(String(64), nullable=False, unique=True, index=True)
    correlation_id = Column(String(64), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    agent_id = Column(String(128), nullable=True)
    operation = Column(String(255), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    error_summary = Column(String(500), nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
