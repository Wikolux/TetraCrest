from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Text
from sqlalchemy.sql import func

from database import Base


class EveningReflectionRecord(Base):
    """The durable row shape for Personal OS's own EveningReflection
    (Application-owned structured state, mirroring DailyIntentRecord's own
    precedent exactly - not a Memory Framework row).

    Always a new row, never edited after creation (§9's own "written the
    same day it reflects on, never backfilled or edited after the fact").
    daily_intent_id links today's reflection back to today's morning
    DailyIntentRecord, so "what did I originally plan" and "what actually
    happened" both stay independently recoverable (P2 §5).

    reconciliation_json and reasoning_trace_json are JSON-serialized lists
    (matching DailyIntentRecord's own precedent for variable-shape
    content): reconciliation_json is one entry per planned activity
    (description, status, evidence); reasoning_trace_json preserves the
    fact/inferred-pattern/user-explanation/hypothesis/recommendation chain
    as evidence for a future pattern-analysis milestone (P2 §9) - never a
    pattern engine itself, just the raw material one would need.
    """

    __tablename__ = "evening_reflection_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reflection_date = Column(Date, nullable=False, index=True)
    daily_intent_id = Column(Integer, ForeignKey("daily_intent_records.id"), nullable=True, index=True)
    accomplishments_json = Column(Text, nullable=False, default="[]")
    unexpected_events_json = Column(Text, nullable=False, default="[]")
    lessons_json = Column(Text, nullable=False, default="[]")
    decisions_json = Column(Text, nullable=False, default="[]")
    worth_remembering_json = Column(Text, nullable=False, default="[]")
    preparation_for_tomorrow_json = Column(Text, nullable=False, default="[]")
    reconciliation_json = Column(Text, nullable=False, default="[]")
    reasoning_trace_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
