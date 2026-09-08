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
