import httpx
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled


class _FakeSnippet:
    def __init__(self, text: str):
        self.text = text


def _fake_fetch_success(monkeypatch, texts: list[str]):
    def _fetch(self, video_id, languages=("en",), preserve_formatting=False):
        return [_FakeSnippet(t) for t in texts]

    monkeypatch.setattr(YouTubeTranscriptApi, "fetch", _fetch)


def _fake_fetch_no_transcript(monkeypatch):
    def _fetch(self, video_id, languages=("en",), preserve_formatting=False):
        raise TranscriptsDisabled(video_id)

    monkeypatch.setattr(YouTubeTranscriptApi, "fetch", _fetch)


def _fake_oembed(monkeypatch, title: str = "Test Video", author_name: str = "Test Channel"):
    def _get(url, **kwargs):
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            json={"title": title, "author_name": author_name},
            request=request,
        )

    monkeypatch.setattr(httpx, "get", _get)


def test_successful_transcript_ingestion(client, org_id, monkeypatch):
    _fake_fetch_success(monkeypatch, ["Hello there.", "This is a transcript."])
    _fake_oembed(monkeypatch)

    response = client.post(
        "/api/v1/knowledge/ingest/youtube",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "organization_id": org_id,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "youtube"
    assert body["source_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert body["title"] == "Test Video"
    assert body["content"] == "Hello there. This is a transcript."
    assert body["ingestion_status"] == "completed"
    assert body["organization_id"] == org_id

    metadata = __import__("json").loads(body["metadata_json"])
    assert metadata == {"video_id": "dQw4w9WgXcQ", "channel": "Test Channel"}


def test_short_url_form_is_supported(client, org_id, monkeypatch):
    _fake_fetch_success(monkeypatch, ["Short link works."])
    _fake_oembed(monkeypatch)

    response = client.post(
        "/api/v1/knowledge/ingest/youtube",
        json={"url": "https://youtu.be/dQw4w9WgXcQ", "organization_id": org_id},
    )

    assert response.status_code == 201
    assert response.json()["content"] == "Short link works."


def test_malformed_url_is_rejected(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/youtube",
        json={"url": "not-a-url", "organization_id": org_id},
    )

    assert response.status_code == 400


def test_invalid_youtube_url_is_rejected(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/youtube",
        json={"url": "https://example.com/watch?v=dQw4w9WgXcQ", "organization_id": org_id},
    )

    assert response.status_code == 400


def test_youtube_url_missing_video_id_is_rejected(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/youtube",
        json={"url": "https://www.youtube.com/watch", "organization_id": org_id},
    )

    assert response.status_code == 400


def test_missing_transcript_returns_404(client, org_id, monkeypatch):
    _fake_fetch_no_transcript(monkeypatch)
    _fake_oembed(monkeypatch)

    response = client.post(
        "/api/v1/knowledge/ingest/youtube",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "organization_id": org_id,
        },
    )

    assert response.status_code == 404


def test_metadata_persists_and_is_retrievable(client, org_id, monkeypatch):
    _fake_fetch_success(monkeypatch, ["Persisted transcript content."])
    _fake_oembed(monkeypatch, title="Persisted Title", author_name="Persisted Channel")

    create_resp = client.post(
        "/api/v1/knowledge/ingest/youtube",
        json={
            "url": "https://www.youtube.com/watch?v=abc12345678",
            "organization_id": org_id,
        },
    )
    assert create_resp.status_code == 201
    document_id = create_resp.json()["id"]

    list_resp = client.get(f"/api/v1/knowledge/organization/{org_id}")
    assert list_resp.status_code == 200
    stored = next(d for d in list_resp.json() if d["id"] == document_id)

    assert stored["source_type"] == "youtube"
    assert stored["source_url"] == "https://www.youtube.com/watch?v=abc12345678"
    assert stored["title"] == "Persisted Title"
    assert stored["content"] == "Persisted transcript content."
    assert stored["ingestion_status"] == "completed"

    metadata = __import__("json").loads(stored["metadata_json"])
    assert metadata == {"video_id": "abc12345678", "channel": "Persisted Channel"}


def test_explicit_title_overrides_metadata_title(client, org_id, monkeypatch):
    _fake_fetch_success(monkeypatch, ["Some transcript."])
    _fake_oembed(monkeypatch, title="Fetched Title")

    response = client.post(
        "/api/v1/knowledge/ingest/youtube",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "organization_id": org_id,
            "title": "My Custom Title",
        },
    )

    assert response.status_code == 201
    assert response.json()["title"] == "My Custom Title"


def test_metadata_fetch_failure_falls_back_gracefully(client, org_id, monkeypatch):
    _fake_fetch_success(monkeypatch, ["Transcript without metadata."])

    def _get(url, **kwargs):
        raise httpx.ConnectError("boom", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", _get)

    response = client.post(
        "/api/v1/knowledge/ingest/youtube",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "organization_id": org_id,
        },
    )

    assert response.status_code == 201
    body = response.json()
    # falls back to the URL when metadata (and thus title) can't be fetched
    assert body["title"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert body["content"] == "Transcript without metadata."
