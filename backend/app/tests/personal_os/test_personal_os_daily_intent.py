"""DailyIntent (§4) and DailyIntentRepository - creation, update via a
new version, continuation, new priorities, and rest-day validity."""

from datetime import date

import pytest

from app.services.personal_os.daily_intent import DailyIntent, IntentField, PlannedActivity
from app.services.personal_os.repository import InMemoryDailyIntentRepository
from app.services.personal_os.shared.types import Confidence, DayType, IntentSource


def test_daily_intent_can_be_created_with_minimum_fields():
    intent = DailyIntent(intent_date=date(2026, 8, 13), stated_intention="Work day", day_type=DayType.WORK)
    assert intent.stated_intention == "Work day"
    assert intent.day_type == DayType.WORK
    assert intent.new_priorities == ()
    assert intent.planned_activities == ()


def test_daily_intent_requires_a_stated_intention():
    with pytest.raises(ValueError):
        DailyIntent(intent_date=date(2026, 8, 13), stated_intention="", day_type=DayType.WORK)


def test_daily_intent_rest_day_requires_rest_day_type():
    with pytest.raises(ValueError):
        DailyIntent(intent_date=date(2026, 8, 13), stated_intention="Resting", day_type=DayType.WORK, is_rest_day=True)


def test_rest_day_is_a_valid_intentional_state():
    intent = DailyIntent(intent_date=date(2026, 8, 13), stated_intention="Taking today off", day_type=DayType.REST, is_rest_day=True)
    assert intent.is_rest_day is True
    assert intent.day_type == DayType.REST


def test_new_priorities_carry_their_own_source_and_confidence():
    intent = DailyIntent(
        intent_date=date(2026, 8, 13),
        stated_intention="New plan",
        day_type=DayType.MIXED,
        new_priorities=(IntentField(value="Apply for jobs", source=IntentSource.USER_EXPLICIT, confidence=Confidence.HIGH),),
    )
    assert intent.new_priorities[0].source == IntentSource.USER_EXPLICIT
    assert intent.new_priorities[0].confidence == Confidence.HIGH


def test_planned_activity_requires_a_description():
    with pytest.raises(ValueError):
        PlannedActivity(description="")


# --- repository: creation, versioned update, continuation lookup ---------------------------


def test_repository_save_assigns_an_intent_id():
    repo = InMemoryDailyIntentRepository()
    intent = DailyIntent(intent_date=date(2026, 8, 13), stated_intention="X", day_type=DayType.WORK)
    saved = repo.save(intent, organization_id=1, user_id=2)
    assert saved.intent_id != ""


def test_repository_get_for_date_returns_the_latest_saved_version():
    repo = InMemoryDailyIntentRepository()
    first = DailyIntent(intent_date=date(2026, 8, 13), stated_intention="Plan A", day_type=DayType.WORK)
    repo.save(first, organization_id=1, user_id=2)

    second = DailyIntent(intent_date=date(2026, 8, 13), stated_intention="Plan B (updated)", day_type=DayType.MIXED)
    repo.save(second, organization_id=1, user_id=2)

    latest = repo.get_for_date(organization_id=1, user_id=2, intent_date=date(2026, 8, 13))
    assert latest.stated_intention == "Plan B (updated)"


def test_daily_intent_can_be_updated_without_losing_history():
    """"Updating" is a new version, never an edit - both versions remain
    reachable, matching the platform's own append-only convention."""
    repo = InMemoryDailyIntentRepository()
    v1 = DailyIntent(intent_date=date(2026, 8, 13), stated_intention="Original", day_type=DayType.WORK)
    repo.save(v1, organization_id=1, user_id=2)
    v2 = DailyIntent(intent_date=date(2026, 8, 13), stated_intention="Revised", day_type=DayType.PROJECT)
    repo.save(v2, organization_id=1, user_id=2)

    key = (1, 2, date(2026, 8, 13))
    assert len(repo._by_key[key]) == 2
    assert repo._by_key[key][0].stated_intention == "Original"
    assert repo._by_key[key][1].stated_intention == "Revised"


def test_get_latest_before_finds_continuation_across_a_skipped_day():
    repo = InMemoryDailyIntentRepository()
    monday = DailyIntent(intent_date=date(2026, 8, 10), stated_intention="Monday plan", day_type=DayType.WORK)
    repo.save(monday, organization_id=1, user_id=2)

    # No Tuesday intent saved - Wednesday should still find Monday's.
    latest = repo.get_latest_before(organization_id=1, user_id=2, before=date(2026, 8, 12))
    assert latest.stated_intention == "Monday plan"


def test_get_latest_before_returns_none_when_nothing_precedes_it():
    repo = InMemoryDailyIntentRepository()
    assert repo.get_latest_before(organization_id=1, user_id=2, before=date(2026, 8, 13)) is None


def test_repositories_are_scoped_per_organization_and_user():
    repo = InMemoryDailyIntentRepository()
    mine = DailyIntent(intent_date=date(2026, 8, 13), stated_intention="Mine", day_type=DayType.WORK)
    repo.save(mine, organization_id=1, user_id=2)

    assert repo.get_for_date(organization_id=99, user_id=2, intent_date=date(2026, 8, 13)) is None
    assert repo.get_for_date(organization_id=1, user_id=99, intent_date=date(2026, 8, 13)) is None
