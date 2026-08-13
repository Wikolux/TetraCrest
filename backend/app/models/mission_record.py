from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from database import Base


class MissionRecord(Base):
    """The durable row shape for Personal OS's own Mission (P5) -
    Application-owned structured state, mirroring ExperimentRecord's own
    precedent exactly (a real, stable mission_id column generated once,
    separate from the row's own auto-increment id, since a user may have
    many concurrent or historical missions - see mission_repository.py's
    own module docstring). Every save() is a new row under the same
    mission_id, never an UPDATE (P5 §15's own "a mission must preserve
    history"). autonomy_grants_json is JSON-serialized (matching every
    other nested-content column already established for Pattern/
    Experiment) - see sql_repository.py's own mission-specific
    (de)serialization helpers."""

    __tablename__ = "mission_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mission_id = Column(String(64), nullable=False, index=True)
    objective = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, index=True)
    domain = Column(String(50), nullable=True)
    target_date = Column(Date, nullable=True)
    budget = Column(Text, nullable=False, default="")
    constraints_json = Column(Text, nullable=False, default="[]")
    preferences_json = Column(Text, nullable=False, default="[]")
    related_commitment_ids_json = Column(Text, nullable=False, default="[]")
    autonomy_grants_json = Column(Text, nullable=False, default="[]")
    notes = Column(Text, nullable=False, default="")
    next_step = Column(Text, nullable=False, default="")
    supersedes_mission_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
