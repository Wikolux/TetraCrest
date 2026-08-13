from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from database import Base


class ExperimentRecord(Base):
    """The durable row shape for Personal OS's own Experiment (P4) -
    Application-owned structured state, mirroring PatternRecord's own
    precedent exactly (see experiment_repository.py's own module
    docstring for why this is not an AgentMemory row).

    Every save() is a new row, never an UPDATE - a lifecycle transition
    (approve, activate, review, decide) is a new row under the same
    experiment_id, the same append-only convention every other durable
    Personal OS record already follows.

    baseline_json/comparison_json are JSON-serialized (matching
    PatternRecord's own precedent for nested content) - see
    sql_repository.py's own experiment-specific (de)serialization
    helpers.
    """

    __tablename__ = "experiment_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    experiment_id = Column(String(64), nullable=False, index=True)
    pattern_id = Column(String(64), nullable=False)
    hypothesis_statement = Column(Text, nullable=False)
    adjustment = Column(Text, nullable=False)
    measurement_plan = Column(Text, nullable=False)
    baseline_json = Column(Text, nullable=False)
    started_on = Column(Date, nullable=False)
    review_date = Column(Date, nullable=True)
    status = Column(String(30), nullable=False, index=True)
    comparison_json = Column(Text, nullable=True)
    review_narrative = Column(Text, nullable=False, default="")
    decision = Column(String(20), nullable=True)
    decision_reason = Column(Text, nullable=False, default="")
    review_outcome = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
