"""P7.15: the end-to-end proof this milestone exists to produce - a real
HTTP request through the real FastAPI app, real authentication, real
organization scoping, the real ResearchAgent, the real Tool Framework
(ToolDiscovery -> ToolRegistry -> ToolExecutor -> WikipediaSearchTool),
and the real P7.14 OpenAIConversationProvider chain - with ONLY the two
outbound network calls (Wikipedia, OpenAI) mocked. No layer is bypassed
to simplify this test."""

import httpx
import pytest

from app.models.audit_log import AuditLog


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def token(make_user, org_id):
    return make_user("researcher", org_id)


def _fake_wikipedia_get(url, **kwargs):
    request = httpx.Request("GET", url)
    return httpx.Response(
        200,
        json={"query": {"search": [{"title": "Python (programming language)", "snippet": "Python is a language."}]}},
        request=request,
    )


def _fake_openai_post(url, **kwargs):
    request = httpx.Request("POST", url)
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "model": "gpt-4o-mini",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Python is a popular programming language."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28},
        },
        request=request,
    )


def test_research_lookup_end_to_end_through_every_real_layer(monkeypatch, client, org_id, token, db_session):
    from settings import get_settings

    monkeypatch.setattr(httpx, "get", _fake_wikipedia_get)
    monkeypatch.setattr(httpx, "post", _fake_openai_post)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/research/lookup", json={"query": "python programming"}, headers=_headers(token))
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "Python is a popular programming language." in body["summary"]
    assert any("Python (programming language)" in finding for finding in body["findings"])


def test_research_lookup_requires_authentication(monkeypatch, client, org_id):
    """Zero external calls can occur here structurally: FastAPI rejects
    before the route body - and therefore before any tool/model code -
    ever runs."""

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("no HTTP call should ever be attempted for an unauthenticated request")

    monkeypatch.setattr(httpx, "get", _fail_if_called)
    monkeypatch.setattr(httpx, "post", _fail_if_called)

    response = client.post("/api/v1/research/lookup", json={"query": "python"})

    assert response.status_code == 401


def test_research_lookup_rejects_missing_query_body(client, org_id, token):
    response = client.post("/api/v1/research/lookup", json={}, headers=_headers(token))

    assert response.status_code == 422


def test_research_lookup_records_a_minimal_audit_entry_without_raw_query_content(monkeypatch, client, org_id, token, db_session):
    from settings import get_settings

    monkeypatch.setattr(httpx, "get", _fake_wikipedia_get)
    monkeypatch.setattr(httpx, "post", _fake_openai_post)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        client.post("/api/v1/research/lookup", json={"query": "a very specific private query"}, headers=_headers(token))
    finally:
        get_settings.cache_clear()

    logs = db_session.query(AuditLog).filter(AuditLog.action == "research.lookup").all()
    assert len(logs) == 1
    entry = logs[0]
    assert entry.organization_id == org_id
    assert entry.resource_type == "tool_invocation"
    assert "a very specific private query" not in (entry.details or "")
    assert "wikipedia_search" in entry.details


def test_research_lookup_records_a_failed_audit_entry_when_the_model_call_fails(monkeypatch, client, org_id, token, db_session):
    from settings import get_settings

    def _fake_openai_error(url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}}, request=request)

    monkeypatch.setattr(httpx, "get", _fake_wikipedia_get)
    monkeypatch.setattr(httpx, "post", _fake_openai_error)
    monkeypatch.setenv("OPENAI_API_KEY", "a-bad-key")
    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/research/lookup", json={"query": "python"}, headers=_headers(token))
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["success"] is False

    logs = db_session.query(AuditLog).filter(AuditLog.action == "research.lookup").all()
    assert len(logs) == 1
    import json as _json

    details = _json.loads(logs[0].details)
    assert details["success"] is False


# --- P7.16: the durable execution ledger ------------------------------------------------------


def test_execution_record_is_committed_before_the_wikipedia_call(monkeypatch, client, org_id, token, db_session):
    """P7.16 §9's own hard requirement, proven behaviorally, not just by
    source inspection: at the exact moment the Wikipedia call is made,
    an ExecutionRecord for this request must already be durably
    committed and visible from a COMPLETELY SEPARATE session (db_session,
    not the route's own request-scoped session)."""
    from app.models.execution_record import ExecutionRecord
    from settings import get_settings

    captured = {}

    def _checking_get(url, **kwargs):
        records = db_session.query(ExecutionRecord).filter(ExecutionRecord.organization_id == org_id).all()
        captured["count_at_call_time"] = len(records)
        captured["status_at_call_time"] = records[0].status if records else None
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"query": {"search": []}}, request=request)

    monkeypatch.setattr(httpx, "get", _checking_get)
    monkeypatch.setattr(httpx, "post", _fake_openai_post)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        client.post("/api/v1/research/lookup", json={"query": "python"}, headers=_headers(token))
    finally:
        get_settings.cache_clear()

    assert captured["count_at_call_time"] == 1
    assert captured["status_at_call_time"] == "started"


def test_execution_record_reaches_succeeded_after_a_successful_request(monkeypatch, client, org_id, token, db_session):
    from app.core.enums import ExecutionStatus
    from app.models.execution_record import ExecutionRecord
    from settings import get_settings

    monkeypatch.setattr(httpx, "get", _fake_wikipedia_get)
    monkeypatch.setattr(httpx, "post", _fake_openai_post)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        client.post("/api/v1/research/lookup", json={"query": "python"}, headers=_headers(token))
    finally:
        get_settings.cache_clear()

    records = db_session.query(ExecutionRecord).filter(ExecutionRecord.organization_id == org_id).all()
    assert len(records) == 1
    assert records[0].status == ExecutionStatus.SUCCEEDED.value
    assert records[0].finished_at is not None


def test_execution_record_reaches_failed_with_bounded_error_when_the_model_call_fails(monkeypatch, client, org_id, token, db_session):
    from app.core.enums import ExecutionStatus
    from app.models.execution_record import ExecutionRecord
    from settings import get_settings

    def _fake_openai_error(url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}}, request=request)

    monkeypatch.setattr(httpx, "get", _fake_wikipedia_get)
    monkeypatch.setattr(httpx, "post", _fake_openai_error)
    monkeypatch.setenv("OPENAI_API_KEY", "a-bad-key")
    get_settings.cache_clear()
    try:
        client.post("/api/v1/research/lookup", json={"query": "python"}, headers=_headers(token))
    finally:
        get_settings.cache_clear()

    records = db_session.query(ExecutionRecord).filter(ExecutionRecord.organization_id == org_id).all()
    assert len(records) == 1
    assert records[0].status == ExecutionStatus.FAILED.value
    assert records[0].error_summary is not None
    assert "Invalid API key" in records[0].error_summary


def test_unexpected_exception_during_research_marks_the_record_failed_and_still_raises(monkeypatch, client, org_id, token, db_session):
    """P7.16 §15: defense in depth for a genuinely unexpected failure -
    ResearchAgent.research() is designed to never raise, but if something
    still does, the route must attempt to mark FAILED (best-effort)
    before re-raising - never catching/hiding process-level failures."""
    from app.core.enums import ExecutionStatus
    from app.models.execution_record import ExecutionRecord
    from app.services.ai.agents.specialists.research.research_agent import ResearchAgent
    from settings import get_settings

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated unexpected failure")

    monkeypatch.setattr(ResearchAgent, "research", _raise)
    # ResearchAgent's own constructor eagerly builds MemoryAdapter ->
    # AIMemoryService -> ... -> EmbeddingProviderFactory, which validates
    # OPENAI_API_KEY at construction time - unrelated to this test's own
    # concern (a failure inside .research()), but must still be
    # configured for the agent to construct successfully first.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        # Starlette's TestClient re-raises unhandled server exceptions by
        # default (raise_server_exceptions=True, this project's own
        # `client` fixture default) rather than returning a 500 response -
        # exactly the "never silently swallow a genuinely unexpected
        # failure" behavior this test wants to observe.
        with pytest.raises(RuntimeError, match="simulated unexpected failure"):
            client.post("/api/v1/research/lookup", json={"query": "python"}, headers=_headers(token))
    finally:
        get_settings.cache_clear()

    records = db_session.query(ExecutionRecord).filter(ExecutionRecord.organization_id == org_id).all()
    assert len(records) == 1
    assert records[0].status == ExecutionStatus.FAILED.value
    assert records[0].error_summary == "Unexpected exception during research execution"


def test_audit_write_failure_does_not_discard_a_successful_result(monkeypatch, client, org_id, token, db_session):
    """P7.16 §19: the concrete bug the P7.16 audit identified - a
    supplementary AuditLog write failure must never turn an already-
    successful research result into a discarded 500."""
    from app.core.enums import ExecutionStatus
    from app.models.execution_record import ExecutionRecord
    from app.repositories.audit_log_repository import AuditLogRepository
    from settings import get_settings

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated database failure writing the audit row")

    monkeypatch.setattr(AuditLogRepository, "create", _raise)
    monkeypatch.setattr(httpx, "get", _fake_wikipedia_get)
    monkeypatch.setattr(httpx, "post", _fake_openai_post)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/research/lookup", json={"query": "python"}, headers=_headers(token))
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["success"] is True  # the real result reaches the client regardless

    records = db_session.query(ExecutionRecord).filter(ExecutionRecord.organization_id == org_id).all()
    assert records[0].status == ExecutionStatus.SUCCEEDED.value  # the ledger update happened BEFORE the failed audit attempt

    logs = db_session.query(AuditLog).filter(AuditLog.action == "research.lookup").all()
    assert logs == []  # the audit row genuinely was never written


def test_audit_write_failure_leaves_the_session_usable_afterward(monkeypatch, client, org_id, token, db_session):
    """P7.16 §20: a failed commit leaves SQLAlchemy's session in a failed
    transaction state - the route must roll back so the session remains
    usable for whatever runs after it (here: nothing else in this
    request, but proven by confirming the request completes cleanly and
    a subsequent, independent query against the same underlying database
    still works)."""
    from app.repositories.audit_log_repository import AuditLogRepository
    from settings import get_settings

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated database failure writing the audit row")

    monkeypatch.setattr(AuditLogRepository, "create", _raise)
    monkeypatch.setattr(httpx, "get", _fake_wikipedia_get)
    monkeypatch.setattr(httpx, "post", _fake_openai_post)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/research/lookup", json={"query": "python"}, headers=_headers(token))
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    # the underlying database connection is still healthy - a fresh query succeeds
    assert db_session.query(AuditLog).count() == 0


def test_terminal_ledger_update_failure_does_not_fabricate_success_and_still_returns_the_real_result(monkeypatch, client, org_id, token, db_session):
    """P7.16 §21: if mark_succeeded() itself cannot be committed, Tetra
    must not pretend the durable record says SUCCEEDED - it correctly
    stays STARTED - while the client still receives the real, correctly
    produced answer (an explicit, documented policy choice for this
    read-only workflow, not silent data corruption)."""
    from app.core.enums import ExecutionStatus
    from app.models.execution_record import ExecutionRecord
    from app.repositories.execution_record_repository import ExecutionRecordRepository
    from settings import get_settings

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated database failure marking the ledger terminal")

    monkeypatch.setattr(ExecutionRecordRepository, "mark_succeeded", _raise)
    monkeypatch.setattr(httpx, "get", _fake_wikipedia_get)
    monkeypatch.setattr(httpx, "post", _fake_openai_post)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/research/lookup", json={"query": "python"}, headers=_headers(token))
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["success"] is True  # the real answer still reaches the client

    records = db_session.query(ExecutionRecord).filter(ExecutionRecord.organization_id == org_id).all()
    assert len(records) == 1
    assert records[0].status == ExecutionStatus.STARTED.value  # never fabricated to SUCCEEDED

    # the audit step still ran independently, since _try_persist isolates each step
    logs = db_session.query(AuditLog).filter(AuditLog.action == "research.lookup").all()
    assert len(logs) == 1


def test_execution_record_and_audit_log_share_the_same_execution_and_correlation_id(monkeypatch, client, org_id, token, db_session):
    from app.models.execution_record import ExecutionRecord
    from settings import get_settings

    monkeypatch.setattr(httpx, "get", _fake_wikipedia_get)
    monkeypatch.setattr(httpx, "post", _fake_openai_post)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        client.post("/api/v1/research/lookup", json={"query": "python"}, headers=_headers(token))
    finally:
        get_settings.cache_clear()

    record = db_session.query(ExecutionRecord).filter(ExecutionRecord.organization_id == org_id).one()
    log = db_session.query(AuditLog).filter(AuditLog.action == "research.lookup").one()
    import json as _json

    details = _json.loads(log.details)

    assert details["execution_id"] == record.execution_id
    assert details["correlation_id"] == record.correlation_id
