"""HistoricalEvidenceReader / EvidenceWindow (P3 §1, §3): gathering
multi-day evidence from already-durable DailyIntent/EveningReflection
records, and the "similarity/category criteria" heuristic that groups
comparable activities together."""

from datetime import date

from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.evening import EveningReflection, InMemoryEveningReflectionRepository
from app.services.personal_os.pattern_evidence import EvidenceWindow, HistoricalEvidenceReader
from app.services.personal_os.reconciliation import ReconciliationEvidence, reconcile_all
from app.services.personal_os.repository import InMemoryDailyIntentRepository
from app.services.personal_os.shared.types import DayType

ORG_ID, USER_ID = 1, 2


def _seed_day(intent_repo, evening_repo, day, description, *, focus_area="", estimated_hours=None, evidence=None):
    activity = PlannedActivity(description=description, focus_area=focus_area, estimated_hours=estimated_hours)
    intent = DailyIntent(intent_date=day, stated_intention="x", day_type=DayType.WORK, planned_activities=(activity,))
    intent_repo.save(intent, organization_id=ORG_ID, user_id=USER_ID)
    ev = evidence if evidence is not None else ReconciliationEvidence(explicitly_completed=True)
    evidence_by_description = {description: ev}
    reflection = EveningReflection(reflection_date=day, accomplishments=(), evidence_by_activity_description=evidence_by_description)
    reconciliations = reconcile_all((activity,), evidence_by_description)
    evening_repo.save(reflection, reconciliations, organization_id=ORG_ID, user_id=USER_ID, daily_intent_id=intent.intent_id)
    return activity


def _reader():
    intent_repo = InMemoryDailyIntentRepository()
    evening_repo = InMemoryEveningReflectionRepository()
    return HistoricalEvidenceReader(intent_repo, evening_repo), intent_repo, evening_repo


# --- observation window ------------------------------------------------------------------------


def test_evidence_window_trailing_days_computes_the_correct_start():
    window = EvidenceWindow.trailing_days(date(2026, 7, 15), 14)
    assert window.start == date(2026, 7, 1)
    assert window.end == date(2026, 7, 15)


def test_evidence_window_rejects_start_after_end():
    import pytest

    with pytest.raises(ValueError):
        EvidenceWindow(start=date(2026, 7, 15), end=date(2026, 7, 1))


def test_gather_excludes_evidence_outside_the_window():
    reader, intent_repo, evening_repo = _reader()
    _seed_day(intent_repo, evening_repo, date(2026, 7, 1), "Inside window")
    _seed_day(intent_repo, evening_repo, date(2026, 6, 1), "Outside window - too early")

    window = EvidenceWindow(start=date(2026, 6, 25), end=date(2026, 7, 10))
    items = reader.gather(organization_id=ORG_ID, user_id=USER_ID, window=window)

    descriptions = {item.activity_description for item in items}
    assert descriptions == {"Inside window"}


def test_gather_only_returns_evidence_for_the_requested_org_and_user():
    reader, intent_repo, evening_repo = _reader()
    _seed_day(intent_repo, evening_repo, date(2026, 7, 1), "Mine")
    # A different user's evidence, same dates - must never leak across users.
    other_activity = PlannedActivity(description="Someone else's activity")
    other_intent = DailyIntent(intent_date=date(2026, 7, 1), stated_intention="x", day_type=DayType.WORK, planned_activities=(other_activity,))
    intent_repo.save(other_intent, organization_id=ORG_ID, user_id=99)
    other_evidence = {other_activity.description: ReconciliationEvidence(explicitly_completed=True)}
    other_reflection = EveningReflection(reflection_date=date(2026, 7, 1), accomplishments=(), evidence_by_activity_description=other_evidence)
    evening_repo.save(
        other_reflection, reconcile_all((other_activity,), other_evidence), organization_id=ORG_ID, user_id=99, daily_intent_id=other_intent.intent_id
    )

    window = EvidenceWindow(start=date(2026, 7, 1), end=date(2026, 7, 1))
    items = reader.gather(organization_id=ORG_ID, user_id=USER_ID, window=window)
    assert {item.activity_description for item in items} == {"Mine"}


def test_gather_is_traceable_back_to_the_originating_date_and_activity():
    reader, intent_repo, evening_repo = _reader()
    _seed_day(intent_repo, evening_repo, date(2026, 7, 4), "Ship the report")

    window = EvidenceWindow(start=date(2026, 7, 1), end=date(2026, 7, 10))
    items = reader.gather(organization_id=ORG_ID, user_id=USER_ID, window=window)

    assert len(items) == 1
    assert items[0].observation_date == date(2026, 7, 4)
    assert items[0].activity_description == "Ship the report"


def test_gather_carries_estimated_and_actual_hours_when_present():
    reader, intent_repo, evening_repo = _reader()
    _seed_day(
        intent_repo,
        evening_repo,
        date(2026, 7, 4),
        "Study transformers",
        estimated_hours=2.0,
        evidence=ReconciliationEvidence(explicitly_completed=True, actual_hours=4.0),
    )

    window = EvidenceWindow(start=date(2026, 7, 1), end=date(2026, 7, 10))
    items = reader.gather(organization_id=ORG_ID, user_id=USER_ID, window=window)

    assert items[0].estimated_hours == 2.0
    assert items[0].actual_hours == 4.0


def test_gather_handles_missing_duration_data_safely():
    reader, intent_repo, evening_repo = _reader()
    _seed_day(intent_repo, evening_repo, date(2026, 7, 4), "Study transformers")

    window = EvidenceWindow(start=date(2026, 7, 1), end=date(2026, 7, 10))
    items = reader.gather(organization_id=ORG_ID, user_id=USER_ID, window=window)

    assert items[0].estimated_hours is None
    assert items[0].actual_hours is None


def test_gather_categorizes_using_focus_area_when_set():
    reader, intent_repo, evening_repo = _reader()
    _seed_day(intent_repo, evening_repo, date(2026, 7, 4), "Do the thing", focus_area="custom-category")

    window = EvidenceWindow(start=date(2026, 7, 1), end=date(2026, 7, 10))
    items = reader.gather(organization_id=ORG_ID, user_id=USER_ID, window=window)
    assert items[0].activity_category == "custom-category"


def test_gather_falls_back_to_heuristic_category_when_focus_area_is_unset():
    reader, intent_repo, evening_repo = _reader()
    _seed_day(intent_repo, evening_repo, date(2026, 7, 4), "Study AI systems")

    window = EvidenceWindow(start=date(2026, 7, 1), end=date(2026, 7, 10))
    items = reader.gather(organization_id=ORG_ID, user_id=USER_ID, window=window)
    assert items[0].activity_category == "learning"


def test_gather_uses_general_category_when_no_keyword_matches():
    reader, intent_repo, evening_repo = _reader()
    _seed_day(intent_repo, evening_repo, date(2026, 7, 4), "Xyzzy the frobnicator")

    window = EvidenceWindow(start=date(2026, 7, 1), end=date(2026, 7, 10))
    items = reader.gather(organization_id=ORG_ID, user_id=USER_ID, window=window)
    assert items[0].activity_category == "general"
