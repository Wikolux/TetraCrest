"""InMemoryDayEventRepository (P6.1): append-only, sequence-ordered
event log - the same contract SqlDayEventRepository (tested separately,
against a real database, in test_personal_os_sql_repository.py) must
also satisfy."""

from datetime import date

from app.services.personal_os.living_day import DayEvent
from app.services.personal_os.living_day_repository import InMemoryDayEventRepository
from app.services.personal_os.shared.types import DayEventType

ORG_ID, USER_ID = 1, 7
TODAY = date(2026, 8, 14)


def test_append_assigns_sequential_sequence_numbers():
    repo = InMemoryDayEventRepository()
    e1 = repo.append(DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="x"), organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)
    e2 = repo.append(DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED, activity_id="a1"), organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)
    assert e1.sequence == 1
    assert e2.sequence == 2


def test_append_assigns_an_event_id():
    repo = InMemoryDayEventRepository()
    saved = repo.append(DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="x"), organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)
    assert saved.event_id != ""


def test_list_for_day_returns_events_in_append_order():
    repo = InMemoryDayEventRepository()
    repo.append(DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="x"), organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)
    repo.append(DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED, activity_id="a1"), organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)

    events = repo.list_for_day(organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)
    assert [e.event_type for e in events] == [DayEventType.ACTIVITY_ADDED, DayEventType.ACTIVITY_COMPLETED]


def test_list_for_day_returns_empty_tuple_for_an_untouched_day():
    repo = InMemoryDayEventRepository()
    assert repo.list_for_day(organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY) == ()


def test_events_are_never_edited_or_removed_only_appended():
    """The append-only guarantee - nothing in this repository's own
    interface can mutate or delete a prior event."""
    repo = InMemoryDayEventRepository()
    repo.append(DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="x"), organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)
    repo.append(DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED, activity_id="a1"), organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)
    assert len(repo.list_for_day(organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)) == 2
    assert not hasattr(repo, "update")
    assert not hasattr(repo, "delete")


def test_sequences_are_scoped_per_day_not_globally():
    repo = InMemoryDayEventRepository()
    repo.append(DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="x"), organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)
    other_day = date(2026, 8, 15)
    first_on_other_day = repo.append(
        DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="b1", description="y"), organization_id=ORG_ID, user_id=USER_ID, day_date=other_day
    )
    assert first_on_other_day.sequence == 1


def test_repository_scopes_by_organization_and_user():
    repo = InMemoryDayEventRepository()
    repo.append(DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="x"), organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)
    repo.append(DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="x"), organization_id=ORG_ID, user_id=99, day_date=TODAY)

    assert len(repo.list_for_day(organization_id=ORG_ID, user_id=USER_ID, day_date=TODAY)) == 1
