"""Living Day State (P6.1): the user's day as a continuously adaptable
state, never a fixed morning schedule - "the OS should adapt to reality
as the day changes... it should never assume that the original morning
plan remains valid."

Three concepts, kept structurally distinct so none of them are ever
silently conflated:

1. DailyIntent (daily_intent.py, P1) - the ORIGINAL morning intent.
   Never rewritten by anything in this module; LivingDayState.
   original_intent is always the same record the morning flow saved.
2. DayEvent - one real thing that happened during the day (an activity
   was added/completed/postponed/held/resumed/removed, an unexpected
   event occurred, available time changed, day mode changed). Append-
   only: a DayEvent is never edited or deleted, only recorded, via
   living_day_repository.py.
3. LivingDayState - the CURRENT state, always derived by folding the
   full, ordered event history over the original intent (reconstruct()
   below) - never itself the source of truth, never persisted as a
   snapshot. "The current state should be reconstructable from persisted
   history" (P6.1's own explicit requirement) is true by construction:
   there is no separate current-state row that could drift from the
   event log, because there is no such row at all.

Activity identity: an activity seeded from the morning's own DailyIntent
gets a stable, deterministic id (intent_activity_id(), matching
candidate_sources.py's own `f"intent:{date}:{description}"` convention
exactly, so the two modules never disagree about what a given morning
activity's own id is). An activity created mid-day (ACTIVITY_ADDED,
UNEXPECTED_EVENT) gets a fresh id assigned by whoever emits that event
(living_day_flow.py or living_day_interaction.py) - always a real,
caller-supplied string, never generated silently inside reconstruct()
itself, since reconstruct() is a pure fold with no side effects of its
own.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from app.services.personal_os.daily_intent import DailyIntent
from app.services.personal_os.day_mode import DayMode
from app.services.personal_os.shared.types import DayEventType, LifeDomain, LivingActivityStatus

DEFAULT_AVAILABLE_HOURS = 8.0

# Reversible via ACTIVITY_RESUMED only from these statuses - resuming a
# COMPLETED or REMOVED activity is not "resuming," it is a new decision,
# so RESUMED is a no-op (see reconstruct()) unless the activity is
# currently HELD.
_RESUMABLE_STATUSES = (LivingActivityStatus.HELD,)


def intent_activity_id(intent_date: date, description: str) -> str:
    """The stable id a morning-seeded activity always has - identical to
    candidate_sources.from_daily_intent()'s own item_id convention, so an
    event targeting this activity (e.g. ACTIVITY_COMPLETED) can always be
    constructed without first querying anything."""
    return f"intent:{intent_date.isoformat()}:{description}"


@dataclass(frozen=True)
class DayEvent:
    """One real, append-only fact about the day - never a whole-state
    snapshot. Only the fields relevant to `event_type` are meaningful for
    any given event (the same "one flat record, several optional
    payload fields, only the relevant ones populated" shape
    reconciliation.py's own ReconciliationEvidence already established);
    reconstruct() reads exactly the fields each event_type defines below.

    - ACTIVITY_ADDED / UNEXPECTED_EVENT: activity_id (fresh, caller-
      assigned), description, domain, deadline, estimated_hours.
    - ACTIVITY_COMPLETED / ACTIVITY_POSTPONED / ACTIVITY_HELD /
      ACTIVITY_RESUMED / ACTIVITY_REMOVED: activity_id (must already
      exist), reason (optional).
    - AVAILABLE_TIME_CHANGED: available_hours (the new total, not a
      delta - explicit is safer than accumulating deltas across an
      unbounded event log).
    - DAY_MODE_CHANGED: day_mode.
    """

    event_type: DayEventType
    activity_id: str = ""
    description: str = ""
    domain: LifeDomain | None = None
    deadline: date | None = None
    estimated_hours: float | None = None
    reason: str = ""
    available_hours: float | None = None
    day_mode: DayMode | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    sequence: int = 0
    event_id: str = ""

    def __post_init__(self) -> None:
        if self.event_type in (DayEventType.ACTIVITY_ADDED, DayEventType.UNEXPECTED_EVENT):
            if not self.activity_id:
                raise ValueError(f"DayEvent({self.event_type.value}) requires activity_id")
            if not self.description:
                raise ValueError(f"DayEvent({self.event_type.value}) requires description")
        elif self.event_type in (
            DayEventType.ACTIVITY_COMPLETED,
            DayEventType.ACTIVITY_POSTPONED,
            DayEventType.ACTIVITY_HELD,
            DayEventType.ACTIVITY_RESUMED,
            DayEventType.ACTIVITY_REMOVED,
        ):
            if not self.activity_id:
                raise ValueError(f"DayEvent({self.event_type.value}) requires activity_id")
        elif self.event_type == DayEventType.AVAILABLE_TIME_CHANGED:
            if self.available_hours is None:
                raise ValueError("DayEvent(available_time_changed) requires available_hours")
            if self.available_hours < 0:
                raise ValueError("DayEvent.available_hours must not be negative")
        elif self.event_type == DayEventType.DAY_MODE_CHANGED:
            if self.day_mode is None:
                raise ValueError("DayEvent(day_mode_changed) requires day_mode")


@dataclass(frozen=True)
class LivingActivity:
    """One activity's own current, derived state - never itself
    persisted; always rebuilt fresh by reconstruct(). is_unexpected marks
    an activity that originated from an UNEXPECTED_EVENT rather than the
    morning plan or a deliberate mid-day addition, so a caller can tell
    "I planned this and it changed" apart from "this wasn't planned at
    all," without needing to re-scan the event log itself."""

    activity_id: str
    description: str
    status: LivingActivityStatus
    domain: LifeDomain | None = None
    deadline: date | None = None
    estimated_hours: float | None = None
    is_unexpected: bool = False
    last_reason: str = ""


@dataclass(frozen=True)
class LivingDayState:
    """The reconstructed current view of one day - original_intent is
    the untouched morning record (P6.1's own "the original intent must
    never be silently rewritten"); activities/available_hours/day_mode
    are all derived by folding `events` (the complete, ordered history)
    over it. Two independent calls to reconstruct() with the same inputs
    always produce an identical LivingDayState (pure function, no
    hidden state)."""

    day_date: date
    original_intent: DailyIntent | None
    activities: tuple[LivingActivity, ...]
    available_hours: float
    day_mode: DayMode | None
    events: tuple[DayEvent, ...]

    @property
    def active_activities(self) -> tuple[LivingActivity, ...]:
        return tuple(a for a in self.activities if a.status == LivingActivityStatus.ACTIVE)

    @property
    def held_activities(self) -> tuple[LivingActivity, ...]:
        return tuple(a for a in self.activities if a.status == LivingActivityStatus.HELD)

    def find(self, activity_id: str) -> LivingActivity | None:
        return next((a for a in self.activities if a.activity_id == activity_id), None)


def reconstruct(
    original_intent: DailyIntent | None,
    events: tuple[DayEvent, ...],
    *,
    day_date: date | None = None,
    default_available_hours: float = DEFAULT_AVAILABLE_HOURS,
) -> LivingDayState:
    """The one place events become a current state (P6.1's own "the
    current state should be reconstructable from persisted history") -
    a pure fold, deterministic in the order given (callers pass events
    already ordered by `sequence`, per living_day_repository.py's own
    append-only guarantee). Unrecognized/out-of-order target references
    (an event naming an activity_id that was never added) are silently
    ignored rather than raised - a defensive, honest choice: the event
    log itself is still complete and inspectable even if one event
    turns out to reference something that does not exist, and raising
    here would make reconstruct() fail on data that is still faithfully
    recorded."""
    resolved_day_date = day_date or (original_intent.intent_date if original_intent is not None else None)
    activities: dict[str, LivingActivity] = {}

    if original_intent is not None:
        for activity in original_intent.planned_activities:
            activity_id = intent_activity_id(original_intent.intent_date, activity.description)
            activities[activity_id] = LivingActivity(
                activity_id=activity_id,
                description=activity.description,
                status=LivingActivityStatus.ACTIVE,
                deadline=activity.deadline,
                estimated_hours=activity.estimated_hours,
            )

    available_hours = default_available_hours
    day_mode: DayMode | None = None

    for event in sorted(events, key=lambda e: e.sequence):
        if event.event_type == DayEventType.ACTIVITY_ADDED:
            activities[event.activity_id] = LivingActivity(
                activity_id=event.activity_id,
                description=event.description,
                status=LivingActivityStatus.ACTIVE,
                domain=event.domain,
                deadline=event.deadline,
                estimated_hours=event.estimated_hours,
            )
        elif event.event_type == DayEventType.UNEXPECTED_EVENT:
            activities[event.activity_id] = LivingActivity(
                activity_id=event.activity_id,
                description=event.description,
                status=LivingActivityStatus.COMPLETED,
                domain=event.domain,
                deadline=event.deadline,
                estimated_hours=event.estimated_hours,
                is_unexpected=True,
                last_reason=event.reason,
            )
        elif event.event_type == DayEventType.ACTIVITY_COMPLETED:
            _transition(activities, event.activity_id, LivingActivityStatus.COMPLETED, event.reason)
        elif event.event_type == DayEventType.ACTIVITY_POSTPONED:
            _transition(activities, event.activity_id, LivingActivityStatus.POSTPONED, event.reason)
        elif event.event_type == DayEventType.ACTIVITY_HELD:
            _transition(activities, event.activity_id, LivingActivityStatus.HELD, event.reason)
        elif event.event_type == DayEventType.ACTIVITY_RESUMED:
            current = activities.get(event.activity_id)
            if current is not None and current.status in _RESUMABLE_STATUSES:
                _transition(activities, event.activity_id, LivingActivityStatus.ACTIVE, event.reason)
        elif event.event_type == DayEventType.ACTIVITY_REMOVED:
            _transition(activities, event.activity_id, LivingActivityStatus.REMOVED, event.reason)
        elif event.event_type == DayEventType.AVAILABLE_TIME_CHANGED:
            available_hours = event.available_hours if event.available_hours is not None else available_hours
        elif event.event_type == DayEventType.DAY_MODE_CHANGED:
            day_mode = event.day_mode

    return LivingDayState(
        day_date=resolved_day_date,
        original_intent=original_intent,
        activities=tuple(activities.values()),
        available_hours=available_hours,
        day_mode=day_mode,
        events=tuple(sorted(events, key=lambda e: e.sequence)),
    )


def _transition(activities: dict[str, LivingActivity], activity_id: str, status: LivingActivityStatus, reason: str) -> None:
    from dataclasses import replace

    current = activities.get(activity_id)
    if current is None:
        return
    activities[activity_id] = replace(current, status=status, last_reason=reason or current.last_reason)
