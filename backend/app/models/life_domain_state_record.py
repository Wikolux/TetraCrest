from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from database import Base


class LifeDomainStateRecord(Base):
    """The durable row shape for Personal OS's own LifeDomainState (P5) -
    Application-owned structured state, mirroring PatternRecord's own
    precedent exactly. Every save() is a new row, never an UPDATE - a
    status change (ACTIVE -> PAUSED -> ACTIVE) is a new row for the same
    (organization, user, domain), the same append-only convention every
    other durable Personal OS record already follows (P5 §6's own
    "must remain historically traceable")."""

    __tablename__ = "life_domain_state_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    domain = Column(String(50), nullable=False, index=True)
    status = Column(String(30), nullable=False)
    classification = Column(String(20), nullable=False)
    objective = Column(Text, nullable=False, default="")
    focus = Column(Text, nullable=False, default="")
    context_notes = Column(Text, nullable=False, default="")
    constraints_json = Column(Text, nullable=False, default="[]")
    deadlines_json = Column(Text, nullable=False, default="[]")
    related_mission_ids_json = Column(Text, nullable=False, default="[]")
    last_reviewed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    supersedes_state_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
