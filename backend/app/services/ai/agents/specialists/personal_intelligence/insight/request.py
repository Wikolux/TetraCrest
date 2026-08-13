"""InsightRequest - what a caller asks the Insight Engine specialist to
do. Not a duplicate of SpecialistRequest or of PersonalIntelligenceRequest
- insight generation's parameters (which analysis to run, how far back to
look, what period a reflection covers) are genuinely different from
either. Kept in its own module (not shared/) since it is InsightAgent's
own entry-point shape, exactly mirroring how
personal_intelligence/shared/request.py holds PersonalIntelligenceRequest
for that agent's entry point.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.services.ai.agents.specialists.personal_intelligence.shared.insight import InsightPeriod


class InsightOperation(StrEnum):
    ANALYZE_PATTERNS = "analyze_patterns"
    IDENTIFY_HABITS = "identify_habits"
    DETECT_CONTRADICTIONS = "detect_contradictions"
    MEASURE_ALIGNMENT = "measure_alignment"
    GENERATE_PERIODIC_REFLECTION = "generate_periodic_reflection"
    GENERATE_RECOMMENDATIONS = "generate_recommendations"
    UPDATE_PROFILE = "update_profile"
    RECALL_INSIGHTS = "recall_insights"


@dataclass(frozen=True)
class InsightRequest:
    operation: InsightOperation
    query: str = ""
    period: InsightPeriod = InsightPeriod.WEEKLY
    lookback_days: int | None = None
    minimum_occurrences: int | None = None
    maximum_memories_analyzed: int | None = None
