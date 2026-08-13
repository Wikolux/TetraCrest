from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from database import Base


class DailyIntentRecord(Base):
    """The durable row shape for Personal OS's own DailyIntent (Application-
    owned structured state - not a Memory Framework row; see
    app/services/personal_os/repository.py's own module docstring for why).

    Every save() is a new row, never an UPDATE - the same append-only,
    never-mutated-in-place convention every other durable record on this
    platform already follows. intent_date is not unique per
    (organization_id, user_id): multiple rows for the same date are the
    day's own version history, and the latest one (highest id) is "the"
    current DailyIntent for that date.

    Nested, variable-shape content (new_priorities, planned_activities,
    focus_areas, known_constraints, deadlines, scheduling_preferences,
    user_provided_changes) is stored JSON-serialized in Text columns,
    matching AuditLog.details's own precedent for structured-but-variable
    content on this platform, rather than introducing a native JSON
    column type nothing else here uses.
    """

    __tablename__ = "daily_intent_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    intent_date = Column(Date, nullable=False, index=True)
    stated_intention = Column(Text, nullable=False)
    day_type = Column(String(50), nullable=False)
    is_rest_day = Column(Boolean, nullable=False, default=False)
    continuation_of_date = Column(Date, nullable=True)
    supersedes_intent_id = Column(String(64), nullable=True)
    new_priorities_json = Column(Text, nullable=False, default="[]")
    planned_activities_json = Column(Text, nullable=False, default="[]")
    focus_areas_json = Column(Text, nullable=False, default="[]")
    known_constraints_json = Column(Text, nullable=False, default="[]")
    deadlines_json = Column(Text, nullable=False, default="[]")
    scheduling_preferences_json = Column(Text, nullable=False, default="[]")
    user_provided_changes_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
