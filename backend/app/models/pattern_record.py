from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from database import Base


class PatternRecord(Base):
    """The durable row shape for Personal OS's own Pattern (P3) -
    Application-owned structured state, mirroring DailyIntentRecord's own
    precedent exactly (see pattern_repository.py's own module docstring
    for why this is not an AgentMemory row).

    Every save() is a new row, never an UPDATE - a status change (e.g.
    PENDING_CONFIRMATION -> CONFIRMED) is a new row referencing the prior
    one via supersedes_pattern_id, the same append-only convention every
    other durable Personal OS record already follows.

    evidence_json, observed_facts_json, possible_hypotheses_json, and
    recommendation_json are JSON-serialized (matching DailyIntentRecord's
    own precedent for variable-shape nested content) - see
    sql_repository.py's own pattern-specific (de)serialization helpers.
    """

    __tablename__ = "pattern_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    pattern_type = Column(String(50), nullable=False, index=True)
    observation_window_start = Column(Date, nullable=False)
    observation_window_end = Column(Date, nullable=False)
    evidence_json = Column(Text, nullable=False, default="[]")
    observed_facts_json = Column(Text, nullable=False, default="[]")
    pattern_statement = Column(Text, nullable=False)
    confidence = Column(String(20), nullable=False)
    possible_hypotheses_json = Column(Text, nullable=False, default="[]")
    user_interpretation = Column(Text, nullable=False, default="")
    recommendation_json = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, index=True)
    supersedes_pattern_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
