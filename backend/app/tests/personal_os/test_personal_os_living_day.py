"""Living Day State (P6.1): DayEvent validation, activity capabilities
(add/complete/postpone/hold/resume/remove/unexpected/time-changed/mode-
changed), and reconstruct()'s own pure-fold determinism - the original
morning intent must never be silently rewritten, and the current state
must always be reconstructable from persisted history alone."""

from datetime import date

import pytest

from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.day_mode import DayMode
from app.services.personal_os.living_day import DEFAULT_AVAILABLE_HOURS, DayEvent, intent_activity_id, reconstruct
from app.services.personal_os.shared.types import DayEventType, DayModeKind, DayType, LivingActivityStatus

TODAY = date(2026, 8, 14)


def _intent(*activities):
    return DailyIntent(intent_date=TODAY, stated_intention="Build Tetra, study, apply for jobs", day_type=DayType.MIXED, planned_activities=activities)


def _seq(events):
    """Assigns sequence numbers in list order, mirroring what a
    repository's own append() would do."""
    return tuple(DayEvent(**{**e.__dict__, "sequence": i + 1}) for i, e in enumerate(events))


# --- DayEvent validation ---------------------------------------------------------------------


def test_activity_added_requires_activity_id_and_description():
    with pytest.raises(ValueError):
        DayEvent(event_type=DayEventType.ACTIVITY_ADDED, description="x")
    with pytest.raises(ValueError):
        DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1")


def test_activity_completed_requires_activity_id():
    with pytest.raises(ValueError):
        DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED)


def test_available_time_changed_requires_non_negative_hours():
    with pytest.raises(ValueError):
        DayEvent(event_type=DayEventType.AVAILABLE_TIME_CHANGED)
    with pytest.raises(ValueError):
        DayEvent(event_type=DayEventType.AVAILABLE_TIME_CHANGED, available_hours=-1.0)


def test_day_mode_changed_requires_a_day_mode():
    with pytest.raises(ValueError):
        DayEvent(event_type=DayEventType.DAY_MODE_CHANGED)


# --- original intent is never rewritten (P6.1) ------------------------------------------------


def test_original_intent_is_preserved_verbatim_through_reconstruction():
    intent = _intent(PlannedActivity(description="Build Tetra Crest"))
    state = reconstruct(intent, ())
    assert state.original_intent is intent
    assert state.original_intent.stated_intention == "Build Tetra, study, apply for jobs"


def test_reconstruct_with_no_intent_and_no_events_is_a_valid_starting_state():
    """§ 'A user may say I don't have plans today / I don't know yet' -
    all should be valid starting states."""
    state = reconstruct(None, (), day_date=TODAY)
    assert state.original_intent is None
    assert state.activities == ()
    assert state.available_hours == DEFAULT_AVAILABLE_HOURS


# --- the nine required capabilities -------------------------------------------------------------


def test_activity_added():
    events = _seq([DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="Buy a gift")])
    state = reconstruct(None, events, day_date=TODAY)
    assert state.find("a1").status == LivingActivityStatus.ACTIVE
    assert state.find("a1").description == "Buy a gift"


def test_activity_completed():
    events = _seq(
        [
            DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="Buy a gift"),
            DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED, activity_id="a1", reason="done"),
        ]
    )
    state = reconstruct(None, events, day_date=TODAY)
    assert state.find("a1").status == LivingActivityStatus.COMPLETED
    assert state.find("a1").last_reason == "done"


def test_activity_postponed():
    intent = _intent(PlannedActivity(description="Apply for jobs"))
    activity_id = intent_activity_id(TODAY, "Apply for jobs")
    events = _seq([DayEvent(event_type=DayEventType.ACTIVITY_POSTPONED, activity_id=activity_id, reason="ran out of time")])
    state = reconstruct(intent, events, day_date=TODAY)
    assert state.find(activity_id).status == LivingActivityStatus.POSTPONED


def test_activity_held():
    intent = _intent(PlannedActivity(description="Study system design"))
    activity_id = intent_activity_id(TODAY, "Study system design")
    events = _seq([DayEvent(event_type=DayEventType.ACTIVITY_HELD, activity_id=activity_id)])
    state = reconstruct(intent, events, day_date=TODAY)
    assert state.find(activity_id).status == LivingActivityStatus.HELD
    assert state.held_activities == (state.find(activity_id),)


def test_activity_resumed_from_held():
    intent = _intent(PlannedActivity(description="Study system design"))
    activity_id = intent_activity_id(TODAY, "Study system design")
    events = _seq(
        [
            DayEvent(event_type=DayEventType.ACTIVITY_HELD, activity_id=activity_id),
            DayEvent(event_type=DayEventType.ACTIVITY_RESUMED, activity_id=activity_id),
        ]
    )
    state = reconstruct(intent, events, day_date=TODAY)
    assert state.find(activity_id).status == LivingActivityStatus.ACTIVE


def test_activity_resumed_is_a_no_op_from_completed():
    """Resuming only reverses HELD - a completed activity is not
    silently reopened by a RESUMED event."""
    intent = _intent(PlannedActivity(description="Study system design"))
    activity_id = intent_activity_id(TODAY, "Study system design")
    events = _seq(
        [
            DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED, activity_id=activity_id),
            DayEvent(event_type=DayEventType.ACTIVITY_RESUMED, activity_id=activity_id),
        ]
    )
    state = reconstruct(intent, events, day_date=TODAY)
    assert state.find(activity_id).status == LivingActivityStatus.COMPLETED


def test_activity_removed():
    events = _seq(
        [
            DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="Buy a gift"),
            DayEvent(event_type=DayEventType.ACTIVITY_REMOVED, activity_id="a1", reason="changed my mind"),
        ]
    )
    state = reconstruct(None, events, day_date=TODAY)
    assert state.find("a1").status == LivingActivityStatus.REMOVED
    assert state.find("a1") not in state.active_activities


def test_unexpected_event_is_recorded_as_a_completed_unexpected_activity():
    events = _seq([DayEvent(event_type=DayEventType.UNEXPECTED_EVENT, activity_id="m1", description="2-hour meeting", estimated_hours=2.0)])
    state = reconstruct(None, events, day_date=TODAY)
    assert state.find("m1").is_unexpected is True
    assert state.find("m1").status == LivingActivityStatus.COMPLETED
    assert state.find("m1") not in state.active_activities


def test_available_time_changed():
    events = _seq([DayEvent(event_type=DayEventType.AVAILABLE_TIME_CHANGED, available_hours=4.5)])
    state = reconstruct(None, events, day_date=TODAY)
    assert state.available_hours == 4.5


def test_day_mode_changed():
    events = _seq([DayEvent(event_type=DayEventType.DAY_MODE_CHANGED, day_mode=DayMode(kind=DayModeKind.FAMILY_FOCUSED))])
    state = reconstruct(None, events, day_date=TODAY)
    assert state.day_mode.kind == DayModeKind.FAMILY_FOCUSED


# --- postponed/completed are never resurfaced as active (P6.3) ------------------------------------


def test_postponed_activity_is_excluded_from_active_activities():
    intent = _intent(PlannedActivity(description="Apply for jobs"))
    activity_id = intent_activity_id(TODAY, "Apply for jobs")
    events = _seq([DayEvent(event_type=DayEventType.ACTIVITY_POSTPONED, activity_id=activity_id)])
    state = reconstruct(intent, events, day_date=TODAY)
    assert state.active_activities == ()


def test_completed_activity_is_excluded_from_active_activities():
    intent = _intent(PlannedActivity(description="Apply for jobs"))
    activity_id = intent_activity_id(TODAY, "Apply for jobs")
    events = _seq([DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED, activity_id=activity_id)])
    state = reconstruct(intent, events, day_date=TODAY)
    assert state.active_activities == ()


# --- determinism / reconstructability (P6.1) -------------------------------------------------------


def test_reconstruct_is_deterministic():
    intent = _intent(PlannedActivity(description="Build Tetra Crest"))
    events = _seq(
        [
            DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="Buy a gift"),
            DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED, activity_id="a1"),
        ]
    )
    s1 = reconstruct(intent, events, day_date=TODAY)
    s2 = reconstruct(intent, events, day_date=TODAY)
    assert s1.activities == s2.activities
    assert s1.available_hours == s2.available_hours
    assert s1.day_mode == s2.day_mode


def test_reconstruct_orders_events_by_sequence_not_insertion_order():
    """Events passed out of order still fold correctly, since
    reconstruct() sorts by `sequence`, never trusting caller order."""
    add = DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="Buy a gift", sequence=1)
    complete = DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED, activity_id="a1", sequence=2)
    state = reconstruct(None, (complete, add), day_date=TODAY)  # deliberately reversed
    assert state.find("a1").status == LivingActivityStatus.COMPLETED


def test_event_targeting_a_never_added_activity_is_ignored_not_raised():
    """A defensive choice, not a silent failure - the event log itself
    stays complete and inspectable even if one event references an
    activity_id that was never added."""
    events = _seq([DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED, activity_id="does-not-exist")])
    state = reconstruct(None, events, day_date=TODAY)
    assert state.activities == ()
    assert len(state.events) == 1


def test_full_event_history_is_retrievable_from_the_reconstructed_state():
    events = _seq(
        [
            DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="Buy a gift"),
            DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED, activity_id="a1"),
        ]
    )
    state = reconstruct(None, events, day_date=TODAY)
    assert len(state.events) == 2
    assert [e.event_type for e in state.events] == [DayEventType.ACTIVITY_ADDED, DayEventType.ACTIVITY_COMPLETED]
