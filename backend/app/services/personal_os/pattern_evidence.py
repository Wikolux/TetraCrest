"""Historical evidence gathering (P3 §1, §3): the read path every pattern
detector shares, assembling PatternEvidenceItems from the DailyIntent/
EveningReflection records already durably persisted (P1/P2) across a
date window - never a new store, never AgentMemory, purely a read over
what P1/P2 already made durable.

_categorize() is the one heuristic in this module (honestly labeled,
same discipline as morning_flow.py's/evening_flow.py's own free-text
parsing): PlannedActivity.focus_area when the caller actually set it
(the "real" category), or a keyword-derived fallback otherwise - most
activities in practice never have focus_area set, so without a fallback
"similarity/category criteria" (§3) would have almost nothing to group
on.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from app.services.personal_os.daily_intent import DailyIntent
from app.services.personal_os.evening import EveningReflectionRepository
from app.services.personal_os.pattern import PatternEvidenceItem
from app.services.personal_os.repository import DailyIntentRepository

# A small, named keyword-to-category map - not exhaustive, honestly a
# heuristic fallback only. Extending it is a data change, never a reason
# to touch any detector.
_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("learning", ("study", "learn", "read", "course", "research")),
    ("delivery", ("ship", "deploy", "release", "build", "implement", "write")),
    ("communication", ("meeting", "call", "email", "message", "review")),
    ("career", ("apply", "application", "interview", "job", "resume")),
    ("planning", ("plan", "organize", "schedule")),
)


def _categorize(description: str, focus_area: str) -> str:
    if focus_area:
        return focus_area
    lowered = description.lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return category
    return "general"


@dataclass(frozen=True)
class EvidenceWindow:
    """A named observation window - the "relevant time window" §3
    requires, made an explicit, inspectable value rather than two bare
    date arguments passed around."""

    start: date
    end: date

    @classmethod
    def trailing_days(cls, today: date, days: int) -> "EvidenceWindow":
        return cls(start=today - timedelta(days=days), end=today)

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("EvidenceWindow.start must not be after end")


class HistoricalEvidenceReader:
    """Assembles PatternEvidenceItems from durably persisted DailyIntent/
    EveningReflection records - the shared evidence-gathering step every
    detector in pattern_detectors.py starts from, so no detector queries
    the repositories itself."""

    def __init__(self, intent_repository: DailyIntentRepository, evening_repository: EveningReflectionRepository) -> None:
        self.intent_repository = intent_repository
        self.evening_repository = evening_repository

    def gather(self, *, organization_id: int, user_id: int, window: EvidenceWindow) -> tuple[PatternEvidenceItem, ...]:
        intents_by_date: dict[date, DailyIntent] = {
            intent.intent_date: intent
            for intent in self.intent_repository.list_range(
                organization_id=organization_id, user_id=user_id, start=window.start, end=window.end
            )
        }
        reconciliation_pairs = self.evening_repository.list_reconciliations_range(
            organization_id=organization_id, user_id=user_id, start=window.start, end=window.end
        )

        items = []
        for observation_date, record in reconciliation_pairs:
            intent = intents_by_date.get(observation_date)
            planned = None
            if intent is not None:
                planned = next(
                    (a for a in intent.planned_activities if a.description == record.activity.description), None
                )
            estimated_hours = planned.estimated_hours if planned is not None else record.activity.estimated_hours
            focus_area = planned.focus_area if planned is not None else record.activity.focus_area
            items.append(
                PatternEvidenceItem(
                    observation_date=observation_date,
                    activity_description=record.activity.description,
                    activity_category=_categorize(record.activity.description, focus_area),
                    status=record.status.value,
                    estimated_hours=estimated_hours,
                    actual_hours=record.evidence.actual_hours,
                    stated_reason=record.evidence.note or record.evidence.superseding_priority,
                )
            )
        return tuple(sorted(items, key=lambda item: item.observation_date))
