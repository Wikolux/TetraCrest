from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from database import Base


class DayEventRecord(Base):
    """The durable row shape for Personal OS's own DayEvent (P6.1) -
    Application-owned structured state, one row per real, append-only
    fact about a day (never a whole-day snapshot; see living_day.py's
    own module docstring for why this is shaped as an event log rather
    than a versioned entity like PatternRecord/ExperimentRecord).

    Rows are NEVER updated or deleted - every save is an INSERT, and
    `sequence` (assigned by SqlDayEventRepository at append time) is the
    authoritative ordering living_day.reconstruct() folds over, not
    `occurred_at` (which exists for human-readable context only and
    could theoretically collide at sub-second resolution).

    day_mode_kind/day_mode_custom_label/day_mode_stated_by_user flatten
    DayEvent.day_mode's own small shape into plain columns rather than
    JSON, since DayMode has no nested/variable-length content worth a
    serialized blob (matching PatternRecord's own "confidence" column -
    a simple value gets a simple column, JSON is reserved for genuinely
    nested content elsewhere in this package)."""

    __tablename__ = "day_event_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    day_date = Column(Date, nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    event_type = Column(String(30), nullable=False)
    activity_id = Column(String(128), nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    domain = Column(String(50), nullable=True)
    deadline = Column(Date, nullable=True)
    estimated_hours = Column(Float, nullable=True)
    reason = Column(Text, nullable=False, default="")
    available_hours = Column(Float, nullable=True)
    day_mode_kind = Column(String(30), nullable=True)
    day_mode_custom_label = Column(String(255), nullable=True)
    day_mode_stated_by_user = Column(Boolean, nullable=True)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
