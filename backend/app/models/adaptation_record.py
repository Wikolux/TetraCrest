from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from database import Base


class AdaptationRecord(Base):
    """The durable row shape for Personal OS's own Adaptation (P7.10) -
    Application-owned structured state, mirroring ExperimentRecord's own
    precedent exactly: a real, stable adaptation_id column generated once
    at the first save, separate from the row's own auto-increment id,
    since a user may have many concurrent or historical adaptations
    across all four scopes. Every save() is a new row under the same
    adaptation_id, never an UPDATE - a lifecycle transition (evaluate,
    approve, adopt, roll back, retire) is a new version, so the full
    history is always retrievable, never overwritten (P7.10 §13's own
    "do not rewrite history")."""

    __tablename__ = "adaptation_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    adaptation_id = Column(String(64), nullable=False, index=True)
    scope = Column(String(30), nullable=False, index=True)
    target_id = Column(String(128), nullable=False, index=True)
    pattern_id = Column(String(64), nullable=False)
    confidence = Column(String(20), nullable=False)
    expected_outcome = Column(Text, nullable=False, default="")
    experiment_id = Column(String(64), nullable=True)
    status = Column(String(30), nullable=False, index=True)
    supersedes_adaptation_id = Column(String(64), nullable=True)
    decision_reason = Column(Text, nullable=False, default="")
    effect_kind = Column(String(30), nullable=True)
    effect_direction = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
