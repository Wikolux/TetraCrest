"""P7.19: proves the real API-only data path that was previously
structurally impossible (per the P7.19 Phase 0 audit) now produces real
Pattern evidence - end to end, through real HTTP for intent/reflect, with
no manually fabricated PlannedActivity or ReconciliationRecord anywhere
after authentication. This is the single required proof of this
milestone: DATA READINESS, not detector activation (Pattern detection
itself remains untriggered in production, per the brief's own explicit
scope)."""

from datetime import UTC, datetime

from app.models.daily_intent_record import DailyIntentRecord
from app.services.personal_os.pattern_detectors import PatternDetectionConfig, detect_all
from app.services.personal_os.pattern_evidence import EvidenceWindow, HistoricalEvidenceReader
from app.services.personal_os.sql_repository import SqlDailyIntentRepository, SqlEveningReflectionRepository


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_real_api_activity_produces_real_pattern_evidence(client, org_id, make_user, db_session):
    token = make_user("alice", org_id)

    # 1-2: real authenticated intent submission with structured planned activities
    intent_response = client.post(
        "/api/v1/personal-os/today/intent",
        json={
            "text": "Focused work day",
            "planned_activities": [
                {"description": "Write the quarterly report", "focus_area": "delivery"},
                {"description": "Review the budget"},
            ],
        },
        headers=_headers(token),
    )
    assert intent_response.status_code == 200

    # 3: persisted DailyIntent actually contains them
    intent_records = db_session.query(DailyIntentRecord).filter(DailyIntentRecord.organization_id == org_id).all()
    assert len(intent_records) == 1
    assert "Write the quarterly report" in intent_records[0].planned_activities_json
    assert "Review the budget" in intent_records[0].planned_activities_json

    # 4: EveningReflectionFlow.submit() requires nothing beyond the intent itself -
    # no interim /today/interact call is required to reach reconciliation.

    # 5: real reflection through the real API, resolving both activities unambiguously
    reflect_response = client.post(
        "/api/v1/personal-os/today/reflect",
        json={"text": "I finished writing the quarterly report. Review the budget - priorities changed, so I postponed it."},
        headers=_headers(token),
    )
    assert reflect_response.status_code == 200
    assert reflect_response.json()["needs_follow_up"] is False

    # 6-7: real, persisted ReconciliationRecords, read through the real repository
    today = datetime.now(UTC).date()
    reconciliation_pairs = SqlEveningReflectionRepository(db_session).list_reconciliations_range(
        organization_id=org_id, user_id=intent_records[0].user_id, start=today, end=today
    )
    assert len(reconciliation_pairs) == 2
    descriptions = {record.activity.description for _date, record in reconciliation_pairs}
    assert descriptions == {"Write the quarterly report", "Review the budget"}

    # 8-9: HistoricalEvidenceReader, constructed with real repositories, against real persisted state
    reader = HistoricalEvidenceReader(
        intent_repository=SqlDailyIntentRepository(db_session), evening_repository=SqlEveningReflectionRepository(db_session)
    )
    window = EvidenceWindow(start=today, end=today)
    evidence = reader.gather(organization_id=org_id, user_id=intent_records[0].user_id, window=window)

    # 10: non-empty, real evidence - the central proof of this milestone
    assert len(evidence) == 2

    # §29 source-trace: request description -> DailyIntent -> ReconciliationRecord -> PatternEvidenceItem, by field name
    evidence_by_description = {item.activity_description: item for item in evidence}
    assert set(evidence_by_description) == {"Write the quarterly report", "Review the budget"}
    assert evidence_by_description["Write the quarterly report"].status == "completed"
    assert evidence_by_description["Review the budget"].status == "superseded"

    # §31: documents the current activity_category value - a real, honest snapshot
    # of the existing vocabulary mismatch (activity_category vs LifeDomain), not a fix.
    # focus_area was set explicitly for this one, so it becomes the category verbatim;
    # the other falls through _categorize()'s own keyword heuristic ("review" -> "communication").
    assert evidence_by_description["Write the quarterly report"].activity_category == "delivery"
    assert evidence_by_description["Review the budget"].activity_category == "communication"

    # §30: PatternDetectionFlow.detect()'s own composition can now be handed this real
    # evidence directly - no fabricated input required. A 2-observation set is
    # legitimately below every detector's min_observations=3, so no Pattern is
    # expected to be actually detected here (that is a detector-activation
    # question, explicitly out of scope for this milestone) - the assertion that
    # matters is that detect_all() runs against real, non-empty, valid evidence.
    patterns = detect_all(evidence, PatternDetectionConfig(), lambda: "test-pattern-id")
    assert isinstance(patterns, tuple)
