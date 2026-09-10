"""P7.17: real end-to-end API tests for Personal OS's own five routes -
real HTTP through the real app, real authentication, real tenant
scoping, and the real, unmodified Personal OS flows underneath. Only the
outbound OpenAI HTTP call is ever mocked, matching every other real-
integration test on this platform (test_research_lookup_route.py)."""

from datetime import UTC, datetime

import httpx
import pytest

from app.models.daily_intent_record import DailyIntentRecord
from app.models.day_event_record import DayEventRecord
from app.models.evening_reflection_record import EveningReflectionRecord
from app.models.user import User
from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.shared.types import DayType
from app.services.personal_os.sql_repository import SqlDailyIntentRepository


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


@pytest.fixture()
def token(make_user, org_id):
    return make_user("alice", org_id)


def _fake_openai_success(url, **kwargs):
    request = httpx.Request("POST", url)
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "model": "gpt-4o-mini",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Understood - treating today as planned."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        },
        request=request,
    )


def _fake_openai_error(url, **kwargs):
    request = httpx.Request("POST", url)
    return httpx.Response(401, json={"error": {"message": "Invalid API key"}}, request=request)


def _fake_openai_embeddings(url, **kwargs):
    """PersonalStateReader() -> ... -> EmbeddingProviderFactory.create()
    eagerly builds a real OpenAIEmbeddingProvider regardless of whether
    this read path needs semantic search - an existing platform
    dependency GET /brief inherits unmodified (see Known Limitations in
    the P7.17 closure report). Mocked here so no live network call is
    ever made, matching every other test on this platform."""
    request = httpx.Request("POST", url)
    if "embeddings" in str(url):
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.0] * 8}]}, request=request)
    return _fake_openai_success(url, **kwargs)


# --- AUTHENTICATION --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "/api/v1/personal-os/today", None),
        ("post", "/api/v1/personal-os/today/intent", {"text": "Work day"}),
        ("post", "/api/v1/personal-os/today/interact", {"text": "add buy milk"}),
        ("post", "/api/v1/personal-os/today/reflect", {"text": "Finished everything"}),
        ("get", "/api/v1/personal-os/brief", None),
    ],
)
def test_all_five_endpoints_reject_unauthenticated_requests(client, org_id, method, path, body):
    call = getattr(client, method)
    response = call(path, json=body) if body is not None else call(path)
    assert response.status_code == 401


# --- IDENTITY ----------------------------------------------------------------------------------


def test_body_cannot_supply_organization_id_user_id_or_today(monkeypatch, client, org_id, token, db_session):
    from settings import get_settings

    monkeypatch.setattr(httpx, "post", _fake_openai_success)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        response = client.post(
            "/api/v1/personal-os/today/intent",
            json={"text": "Work on the launch today", "organization_id": 999999, "user_id": 999999, "today": "2000-01-01"},
            headers=_headers(token),
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    # the fabricated date/identity in the body were never read
    assert body["intent"]["intent_date"] == _today()
    records = db_session.query(DailyIntentRecord).filter(DailyIntentRecord.organization_id == org_id).all()
    assert len(records) == 1
    assert records[0].intent_date.isoformat() == _today()


# --- EMPTY STATE --------------------------------------------------------------------------------


def test_get_today_works_for_a_brand_new_user(client, org_id, token):
    response = client.get("/api/v1/personal-os/today", headers=_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] is None
    assert body["morning_prompt"] is not None
    assert body["living_day"]["activities"] == []
    assert body["priorities"]["core"] == []
    assert body["priorities"]["optional"] == []


def test_get_brief_works_for_a_brand_new_user(monkeypatch, client, org_id, token):
    # PersonalStateReader() -> MemoryAdapter() -> ... -> EmbeddingProviderFactory.create()
    # validates OPENAI_API_KEY at CONSTRUCTION time regardless of whether
    # this read path ever performs semantic search - an existing platform
    # dependency this endpoint inherits unmodified, unrelated to this
    # test's own concern. See Known Limitations in the P7.17 closure report.
    from settings import get_settings

    monkeypatch.setattr(httpx, "post", _fake_openai_embeddings)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        response = client.get("/api/v1/personal-os/brief", headers=_headers(token))
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["brief"] is None
    assert body["note"] is not None
    assert body["personal_state"]["goals"] == []


# --- DAILY LIFECYCLE ----------------------------------------------------------------------------


def test_full_daily_lifecycle_through_real_http(monkeypatch, client, org_id, token, db_session):
    from settings import get_settings

    monkeypatch.setattr(httpx, "post", _fake_openai_success)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        intent_response = client.post(
            "/api/v1/personal-os/today/intent", json={"text": "I need to focus on work today"}, headers=_headers(token)
        )
        assert intent_response.status_code == 200
        assert intent_response.json()["intent"]["day_type"] == "work"
        assert intent_response.json()["acknowledgment"] == "Understood - treating today as planned."

        today_response = client.get("/api/v1/personal-os/today", headers=_headers(token))
        assert today_response.status_code == 200
        assert today_response.json()["intent"] is not None
        assert today_response.json()["morning_prompt"] is None

        interact_response = client.post(
            "/api/v1/personal-os/today/interact", json={"text": "add buying a gift for my wife"}, headers=_headers(token)
        )
        assert interact_response.status_code == 200
        assert interact_response.json()["outcome"] == "events_recorded"
        assert len(interact_response.json()["events"]) == 1

        reflect_response = client.post(
            "/api/v1/personal-os/today/reflect", json={"text": "It was a good day, made real progress"}, headers=_headers(token)
        )
        assert reflect_response.status_code == 200
        assert reflect_response.json()["needs_follow_up"] is False
        assert reflect_response.json()["reflection"] is not None
    finally:
        get_settings.cache_clear()

    # persisted state actually changed through the existing repositories
    assert db_session.query(DailyIntentRecord).filter(DailyIntentRecord.organization_id == org_id).count() == 1
    assert db_session.query(DayEventRecord).filter(DayEventRecord.organization_id == org_id).count() == 1
    assert db_session.query(EveningReflectionRecord).filter(EveningReflectionRecord.organization_id == org_id).count() == 1


# --- MIDDAY INTERACTION --------------------------------------------------------------------------


def test_interact_supported_event_is_recorded(client, org_id, token, db_session):
    response = client.post("/api/v1/personal-os/today/interact", json={"text": "add write the quarterly report"}, headers=_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "events_recorded"
    assert body["events"][0]["event_type"] == "activity_added"
    assert db_session.query(DayEventRecord).filter(DayEventRecord.organization_id == org_id).count() == 1


def test_interact_status_query_does_not_write(client, org_id, token, db_session):
    response = client.post("/api/v1/personal-os/today/interact", json={"text": "what's the plan"}, headers=_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "status_query"
    assert body["events"] == []
    assert db_session.query(DayEventRecord).filter(DayEventRecord.organization_id == org_id).count() == 0


def test_interact_ambiguous_target_asks_for_clarification_and_does_not_write(client, org_id, token, db_session):
    add_a = client.post("/api/v1/personal-os/today/interact", json={"text": "add write proposal for client Aurora"}, headers=_headers(token))
    add_b = client.post("/api/v1/personal-os/today/interact", json={"text": "add write proposal for client Beacon"}, headers=_headers(token))
    assert add_a.status_code == 200
    assert add_b.status_code == 200

    ambiguous = client.post("/api/v1/personal-os/today/interact", json={"text": "I completed the proposal"}, headers=_headers(token))
    assert ambiguous.status_code == 200
    body = ambiguous.json()
    assert body["outcome"] == "clarification_needed"
    assert body["events"] == []
    assert len(body["candidates"]) == 2
    # the two ADD events were recorded, but the ambiguous statement added nothing further
    assert db_session.query(DayEventRecord).filter(DayEventRecord.organization_id == org_id).count() == 2


# --- EVENING -------------------------------------------------------------------------------------


def test_reflect_initial_submission_with_no_planned_activities_needs_no_follow_up(client, org_id, token):
    response = client.post("/api/v1/personal-os/today/reflect", json={"text": "Rested most of the day"}, headers=_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["needs_follow_up"] is False
    assert body["continuation"] is None
    assert body["reflection"] is not None


def test_reflect_follow_up_required_case_and_resolution(client, org_id, token, db_session):
    """Seeds a DailyIntent with real planned_activities directly via the
    repository (exactly as Personal OS's own flow-level tests already
    do) - through the exposed API alone, planned_activities can only ever
    be carried forward from a prior day that itself already had some, so
    reaching the genuinely-ambiguous follow-up path requires seeding one
    directly, the same way any first DailyIntent's own activities would
    have originally been established."""
    user = db_session.query(User).filter(User.username == "alice").one()
    intent = DailyIntent(
        intent_date=datetime.now(UTC).date(),
        stated_intention="Ship the report and call the client",
        day_type=DayType.WORK,
        planned_activities=(PlannedActivity(description="Ship the report"), PlannedActivity(description="Call the client")),
    )
    SqlDailyIntentRepository(db_session).save(intent, organization_id=org_id, user_id=user.id)

    submit_response = client.post(
        "/api/v1/personal-os/today/reflect", json={"text": "I shipped the report"}, headers=_headers(token)
    )
    assert submit_response.status_code == 200
    submit_body = submit_response.json()
    assert submit_body["needs_follow_up"] is True
    assert submit_body["continuation"] is not None
    assert submit_body["reflection"] is None

    follow_up_response = client.post(
        "/api/v1/personal-os/today/reflect",
        json={"text": "priorities changed, something else came up", "continuation": submit_body["continuation"]},
        headers=_headers(token),
    )
    assert follow_up_response.status_code == 200
    follow_up_body = follow_up_response.json()
    assert follow_up_body["needs_follow_up"] is False
    assert follow_up_body["reflection"] is not None
    assert db_session.query(EveningReflectionRecord).filter(EveningReflectionRecord.organization_id == org_id).count() == 1


def test_reflect_continuation_cannot_be_fabricated_by_the_client_to_manufacture_a_reconciliation(client, org_id, token):
    """The client can only ever legitimately obtain a `continuation`
    value from a prior response - constructing one from scratch (as any
    client technically could, since it's plain JSON) is accepted at the
    schema level but has no effect on Personal OS's own real state:
    resolve_follow_up()'s own _finalize() only ever reconciles the
    REAL DailyIntent's own planned_activities (empty here, no intent was
    ever submitted), never the client-supplied `ambiguous_activities`
    list directly - so a fabricated activity name that was never
    actually planned produces zero reconciliations, not a forged one."""
    fabricated_continuation = {
        "ambiguous_activities": [{"description": "A task that was never planned", "focus_area": "", "deadline": None, "estimated_hours": None}],
        "resolved_evidence_by_description": {},
        "resolved_accomplishments": [],
    }
    response = client.post(
        "/api/v1/personal-os/today/reflect",
        json={"text": "it happened", "continuation": fabricated_continuation},
        headers=_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["needs_follow_up"] is False
    assert body["reconciliations"] == []


# --- MODEL ---------------------------------------------------------------------------------------


def test_intent_submission_surfaces_real_model_narration_on_success(monkeypatch, client, org_id, token):
    from settings import get_settings

    monkeypatch.setattr(httpx, "post", _fake_openai_success)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/personal-os/today/intent", json={"text": "Work day"}, headers=_headers(token))
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["acknowledgment"] == "Understood - treating today as planned."


def test_intent_submission_falls_back_honestly_when_the_model_fails(monkeypatch, client, org_id, token):
    from settings import get_settings

    monkeypatch.setattr(httpx, "post", _fake_openai_error)
    monkeypatch.setenv("OPENAI_API_KEY", "a-bad-key")
    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/personal-os/today/intent", json={"text": "Work day"}, headers=_headers(token))
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["acknowledgment"] == "Got it - treating today as a work day."


# --- TENANT ISOLATION ----------------------------------------------------------------------------


def test_user_a_cannot_observe_user_b_or_org_b_state(monkeypatch, client, org_id, make_user, db_session):
    from settings import get_settings

    token_a = make_user("alice", org_id)
    org_b = client.post("/api/v1/organizations", json={"name": "Org B", "slug": "org-b"}).json()["id"]
    token_b = make_user("bob", org_b)

    monkeypatch.setattr(httpx, "post", _fake_openai_embeddings)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        client.post("/api/v1/personal-os/today/intent", json={"text": "Work day for A"}, headers=_headers(token_a))

        today_for_b = client.get("/api/v1/personal-os/today", headers=_headers(token_b))
        assert today_for_b.status_code == 200
        assert today_for_b.json()["intent"] is None  # A's intent is invisible to B

        brief_for_b = client.get("/api/v1/personal-os/brief", headers=_headers(token_b))
    finally:
        get_settings.cache_clear()
    assert brief_for_b.status_code == 200
    assert brief_for_b.json()["brief"] is None

    assert db_session.query(DailyIntentRecord).filter(DailyIntentRecord.organization_id == org_id).count() == 1
    assert db_session.query(DailyIntentRecord).filter(DailyIntentRecord.organization_id == org_b).count() == 0


# --- DATE ------------------------------------------------------------------------------------------


def test_current_date_comes_from_the_authoritative_resolver_not_the_body(client, org_id, token):
    response = client.post(
        "/api/v1/personal-os/today/intent", json={"text": "Work day", "date": "1999-01-01", "today": "1999-01-01"}, headers=_headers(token)
    )
    assert response.status_code == 200
    assert response.json()["intent"]["intent_date"] == _today()


# --- P7.19: STRUCTURED PLANNED ACTIVITY CAPTURE ----------------------------------------------------


def test_text_only_intent_request_remains_backward_compatible(client, org_id, token):
    """No planned_activities field at all - the exact pre-P7.19 request
    shape - must still succeed with the pre-P7.19 empty-activities
    result on a first-time day."""
    response = client.post("/api/v1/personal-os/today/intent", json={"text": "Work day"}, headers=_headers(token))
    assert response.status_code == 200
    assert response.json()["intent"]["planned_activities"] == []


def test_structured_planned_activities_persist_into_daily_intent(client, org_id, token, db_session):
    response = client.post(
        "/api/v1/personal-os/today/intent",
        json={
            "text": "Focused work day",
            "planned_activities": [
                {"description": "Write the quarterly report", "focus_area": "delivery", "estimated_hours": 3.0},
                {"description": "Review the budget", "deadline": "2026-12-31"},
            ],
        },
        headers=_headers(token),
    )
    assert response.status_code == 200
    body = response.json()["intent"]["planned_activities"]
    assert [a["description"] for a in body] == ["Write the quarterly report", "Review the budget"]
    assert body[0]["focus_area"] == "delivery"
    assert body[0]["estimated_hours"] == 3.0
    assert body[1]["deadline"] == "2026-12-31"

    record = db_session.query(DailyIntentRecord).filter(DailyIntentRecord.organization_id == org_id).one()
    assert "Write the quarterly report" in record.planned_activities_json


def test_explicit_empty_planned_activities_list_is_accepted_and_distinct_from_omission(client, org_id, token):
    response = client.post(
        "/api/v1/personal-os/today/intent", json={"text": "Rest day, nothing planned", "planned_activities": []}, headers=_headers(token)
    )
    assert response.status_code == 200
    assert response.json()["intent"]["planned_activities"] == []


def test_missing_description_returns_422(client, org_id, token):
    response = client.post(
        "/api/v1/personal-os/today/intent", json={"text": "Work day", "planned_activities": [{"focus_area": "delivery"}]}, headers=_headers(token)
    )
    assert response.status_code == 422


def test_empty_description_returns_422(client, org_id, token):
    response = client.post(
        "/api/v1/personal-os/today/intent", json={"text": "Work day", "planned_activities": [{"description": ""}]}, headers=_headers(token)
    )
    assert response.status_code == 422


def test_non_positive_estimated_hours_returns_422(client, org_id, token):
    response = client.post(
        "/api/v1/personal-os/today/intent",
        json={"text": "Work day", "planned_activities": [{"description": "x", "estimated_hours": 0}]},
        headers=_headers(token),
    )
    assert response.status_code == 422


def test_invalid_deadline_shape_returns_422(client, org_id, token):
    response = client.post(
        "/api/v1/personal-os/today/intent",
        json={"text": "Work day", "planned_activities": [{"description": "x", "deadline": "not-a-date"}]},
        headers=_headers(token),
    )
    assert response.status_code == 422


def test_unknown_activity_field_is_silently_ignored_matching_project_convention(client, org_id, token):
    """Matches this project's existing schema policy (Pydantic's default
    - ignore, never forbid, unknown fields), the same convention already
    relied on for the organization_id/user_id body-immutability tests."""
    response = client.post(
        "/api/v1/personal-os/today/intent",
        json={"text": "Work day", "planned_activities": [{"description": "x", "priority_score": 99, "status": "done"}]},
        headers=_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["intent"]["planned_activities"][0]["description"] == "x"


def test_duplicate_activity_descriptions_are_preserved_not_deduplicated(client, org_id, token):
    """PlannedActivity has no uniqueness constraint of its own - P7.19
    invents none."""
    response = client.post(
        "/api/v1/personal-os/today/intent",
        json={"text": "Work day", "planned_activities": [{"description": "Same task"}, {"description": "Same task"}]},
        headers=_headers(token),
    )
    assert response.status_code == 200
    descriptions = [a["description"] for a in response.json()["intent"]["planned_activities"]]
    assert descriptions == ["Same task", "Same task"]


def _seed_yesterdays_intent(db_session, org_id, description="Finish the deck"):
    """Real HTTP cannot exercise "yesterday" within one test run (the
    server always resolves "today" to the real current UTC date) - the
    prior day is seeded directly via the repository, exactly as P7.17's
    own reflect-follow-up test seeded a prior DailyIntent, so that
    "today's" submission can still be exercised through the real API."""
    from datetime import UTC, timedelta

    user = db_session.query(User).filter(User.username == "alice").one()
    yesterday = DailyIntent(
        intent_date=datetime.now(UTC).date() - timedelta(days=1), stated_intention="Ship it", day_type=DayType.WORK,
        planned_activities=(PlannedActivity(description=description),),
    )
    SqlDailyIntentRepository(db_session).save(yesterday, organization_id=org_id, user_id=user.id)
    return yesterday


def test_continuation_without_explicit_activities_still_carries_forward(client, org_id, token, db_session):
    _seed_yesterdays_intent(db_session, org_id)

    response = client.post("/api/v1/personal-os/today/intent", json={"text": "Continuing as planned, same as yesterday."}, headers=_headers(token))
    assert response.status_code == 200
    assert [a["description"] for a in response.json()["intent"]["planned_activities"]] == ["Finish the deck"]


def test_continuation_with_explicit_activities_overrides_carry_forward(client, org_id, token, db_session):
    yesterday = _seed_yesterdays_intent(db_session, org_id)

    response = client.post(
        "/api/v1/personal-os/today/intent",
        json={"text": "Continuing as planned, same as yesterday.", "planned_activities": [{"description": "A different task entirely"}]},
        headers=_headers(token),
    )
    assert response.status_code == 200
    assert [a["description"] for a in response.json()["intent"]["planned_activities"]] == ["A different task entirely"]
    assert response.json()["intent"]["continuation_of_date"] == yesterday.intent_date.isoformat()
