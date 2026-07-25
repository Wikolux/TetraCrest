import httpx


def _fake_get(html: str, status_code: int = 200):
    def _get(url, **kwargs):
        request = httpx.Request("GET", url)
        return httpx.Response(status_code, text=html, request=request)

    return _get


def _fake_get_connection_error():
    def _get(url, **kwargs):
        raise httpx.ConnectError("Connection failed", request=httpx.Request("GET", url))

    return _get


VALID_HTML = """
<html>
<head>
<title>Test Page Title</title>
<style>body { color: red; }</style>
</head>
<body>
<script>console.log('should not appear');</script>
<h1>Hello World</h1>
<p>This is a test paragraph.</p>
</body>
</html>
"""

MALFORMED_HTML = """
<html><head><title>Broken Page
<body>
<p>Unclosed paragraph
<div>Some <b>bold and unclosed text
"""


def test_successful_url_ingestion(client, org_id, monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get(VALID_HTML))

    response = client.post(
        "/api/v1/knowledge/ingest/url",
        json={"url": "https://example.com/article", "organization_id": org_id},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "url"
    assert body["source_url"] == "https://example.com/article"
    assert body["title"] == "Test Page Title"
    assert "Hello World" in body["content"]
    assert "This is a test paragraph." in body["content"]
    assert "should not appear" not in body["content"]
    assert "color: red" not in body["content"]
    assert body["ingestion_status"] == "completed"
    assert body["organization_id"] == org_id


def test_invalid_url_is_rejected(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/url",
        json={"url": "not-a-valid-url", "organization_id": org_id},
    )

    assert response.status_code == 400


def test_invalid_scheme_is_rejected(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/url",
        json={"url": "ftp://example.com/file", "organization_id": org_id},
    )

    assert response.status_code == 400


def test_unreachable_url_returns_502(client, org_id, monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get_connection_error())

    response = client.post(
        "/api/v1/knowledge/ingest/url",
        json={"url": "https://example.com/unreachable", "organization_id": org_id},
    )

    assert response.status_code == 502


def test_upstream_error_status_returns_502(client, org_id, monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get("<html>not found</html>", status_code=404))

    response = client.post(
        "/api/v1/knowledge/ingest/url",
        json={"url": "https://example.com/missing", "organization_id": org_id},
    )

    assert response.status_code == 502


def test_malformed_html_does_not_crash(client, org_id, monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get(MALFORMED_HTML))

    response = client.post(
        "/api/v1/knowledge/ingest/url",
        json={"url": "https://example.com/broken", "organization_id": org_id},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["ingestion_status"] == "completed"
    assert "Unclosed paragraph" in body["content"]
    assert "bold and unclosed text" in body["content"]


def test_explicit_title_overrides_extracted_title(client, org_id, monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get(VALID_HTML))

    response = client.post(
        "/api/v1/knowledge/ingest/url",
        json={
            "url": "https://example.com/article",
            "organization_id": org_id,
            "title": "My Custom Title",
        },
    )

    assert response.status_code == 201
    assert response.json()["title"] == "My Custom Title"


def test_metadata_persists_and_is_retrievable(client, org_id, monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get(VALID_HTML))

    create_resp = client.post(
        "/api/v1/knowledge/ingest/url",
        json={"url": "https://example.com/article", "organization_id": org_id},
    )
    assert create_resp.status_code == 201
    document_id = create_resp.json()["id"]

    list_resp = client.get(f"/api/v1/knowledge/organization/{org_id}")
    assert list_resp.status_code == 200
    stored = next(d for d in list_resp.json() if d["id"] == document_id)

    assert stored["source_type"] == "url"
    assert stored["source_url"] == "https://example.com/article"
    assert stored["title"] == "Test Page Title"
    assert "Hello World" in stored["content"]
    assert stored["ingestion_status"] == "completed"
