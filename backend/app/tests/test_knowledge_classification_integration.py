import httpx
from youtube_transcript_api import YouTubeTranscriptApi


class _FakeSnippet:
    def __init__(self, text: str):
        self.text = text


def _fake_html_get(html: str):
    def _get(url, **kwargs):
        request = httpx.Request("GET", url)
        return httpx.Response(200, text=html, request=request)

    return _get


def _fake_oembed_and_transcript(monkeypatch, transcript_texts: list[str], title: str = "Video"):
    def _fetch(self, video_id, languages=("en",), preserve_formatting=False):
        return [_FakeSnippet(t) for t in transcript_texts]

    def _get(url, **kwargs):
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"title": title, "author_name": "Channel"}, request=request)

    monkeypatch.setattr(YouTubeTranscriptApi, "fetch", _fetch)
    monkeypatch.setattr(httpx, "get", _get)


def test_upload_ingestion_classifies_legal_document(client, org_id):
    # The upload endpoint's "content" is a caller-supplied form field (a
    # description), not the uploaded file's bytes - UploadIngestor never
    # extracts text from the file itself, so the classification-relevant
    # text must be passed via "content" here.
    description = (
        "This contract outlines the liability and compliance obligations "
        "under the agreement, including terms and conditions for litigation."
    )

    response = client.post(
        "/api/v1/knowledge/ingest",
        data={
            "organization_id": str(org_id),
            "title": "Master Service Agreement",
            "content": description,
        },
        files={"file": ("contract.txt", b"binary file bytes", "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["classification"] == "Legal"


def test_upload_ingestion_classifies_finance_document(client, org_id):
    description = (
        "This document covers revenue, budget forecast, and the balance "
        "sheet as reviewed in the audit."
    )

    response = client.post(
        "/api/v1/knowledge/ingest",
        data={
            "organization_id": str(org_id),
            "title": "Q3 Financial Report",
            "content": description,
        },
        files={"file": ("finance.txt", b"binary file bytes", "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["classification"] == "Finance"


def test_upload_ingestion_unknown_content_falls_back_to_general(client, org_id):
    description = "Just a bunch of unrelated thoughts about lunch and the weather today."

    response = client.post(
        "/api/v1/knowledge/ingest",
        data={
            "organization_id": str(org_id),
            "title": "Random Notes",
            "content": description,
        },
        files={"file": ("notes.txt", b"binary file bytes", "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["classification"] == "General"


def test_url_ingestion_classifies_product_document(client, org_id, monkeypatch):
    html = """
    <html><head><title>Product Roadmap 2026</title></head>
    <body><p>This roadmap describes upcoming feature requests, the backlog,
    and user story priorities for the MVP.</p></body></html>
    """
    monkeypatch.setattr(httpx, "get", _fake_html_get(html))

    response = client.post(
        "/api/v1/knowledge/ingest/url",
        json={"url": "https://example.com/roadmap", "organization_id": org_id},
    )

    assert response.status_code == 201
    assert response.json()["classification"] == "Product"


def test_youtube_ingestion_classifies_engineering_document(client, org_id, monkeypatch):
    _fake_oembed_and_transcript(
        monkeypatch,
        [
            "This describes the API design, database schema, and deployment "
            "infrastructure for the backend architecture."
        ],
        title="Backend Architecture Overview",
    )

    response = client.post(
        "/api/v1/knowledge/ingest/youtube",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "organization_id": org_id},
    )

    assert response.status_code == 201
    assert response.json()["classification"] == "Engineering"


def test_youtube_ingestion_classifies_marketing_document(client, org_id, monkeypatch):
    _fake_oembed_and_transcript(
        monkeypatch,
        [
            "This campaign covers branding, social media strategy, and "
            "target audience for the new advertisement."
        ],
        title="Q4 Marketing Campaign",
    )

    response = client.post(
        "/api/v1/knowledge/ingest/youtube",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "organization_id": org_id},
    )

    assert response.status_code == 201
    assert response.json()["classification"] == "Marketing"


def test_image_ingestion_classifies_via_title(client, org_id):
    # Image ingestion has no extracted text, but still runs through the same
    # ClassificationService using whatever title/filename signal exists.
    response = client.post(
        "/api/v1/knowledge/ingest/image",
        data={"organization_id": str(org_id), "title": "Q3 Financial Report"},
        files={"file": ("photo.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
    )

    assert response.status_code == 201
    assert response.json()["classification"] == "Finance"
    assert response.json()["content"] == ""


def test_image_ingestion_with_no_signal_falls_back_to_general(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/image",
        data={"organization_id": str(org_id)},
        files={"file": ("photo.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
    )

    assert response.status_code == 201
    assert response.json()["classification"] == "General"


def test_audio_ingestion_classifies_via_title(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/audio",
        data={"organization_id": str(org_id), "title": "Legal Contract Review"},
        files={"file": ("recording.wav", b"RIFFfake", "audio/wav")},
    )

    assert response.status_code == 201
    assert response.json()["classification"] == "Legal"
    assert response.json()["content"] == ""


def test_audio_ingestion_with_no_signal_falls_back_to_general(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/audio",
        data={"organization_id": str(org_id)},
        files={"file": ("recording.wav", b"RIFFfake", "audio/wav")},
    )

    assert response.status_code == 201
    assert response.json()["classification"] == "General"


def test_video_ingestion_classifies_via_title(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/video",
        data={"organization_id": str(org_id), "title": "Sales Pipeline Review"},
        files={"file": ("clip.mp4", b"fake mp4", "video/mp4")},
    )

    assert response.status_code == 201
    assert response.json()["classification"] == "Sales"
    assert response.json()["content"] == ""


def test_video_ingestion_with_no_signal_falls_back_to_general(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/video",
        data={"organization_id": str(org_id)},
        files={"file": ("clip.mp4", b"fake mp4", "video/mp4")},
    )

    assert response.status_code == 201
    assert response.json()["classification"] == "General"


def test_classification_is_persisted_and_retrievable(client, org_id):
    description = (
        "This contract outlines the liability and compliance obligations "
        "under the agreement, including terms and conditions for litigation."
    )

    create_resp = client.post(
        "/api/v1/knowledge/ingest",
        data={
            "organization_id": str(org_id),
            "title": "Master Service Agreement",
            "content": description,
        },
        files={"file": ("contract.txt", b"binary file bytes", "text/plain")},
    )
    assert create_resp.status_code == 201
    document_id = create_resp.json()["id"]
    assert create_resp.json()["classification"] == "Legal"

    list_resp = client.get(f"/api/v1/knowledge/organization/{org_id}")
    assert list_resp.status_code == 200
    stored = next(d for d in list_resp.json() if d["id"] == document_id)
    assert stored["classification"] == "Legal"
