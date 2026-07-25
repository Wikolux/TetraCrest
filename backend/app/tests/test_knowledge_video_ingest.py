from settings import get_settings

_MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"fake-video-data"


def test_successful_upload(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/video",
        data={"organization_id": str(org_id)},
        files={"file": ("clip.mp4", _MP4_BYTES, "video/mp4")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "video"
    assert body["original_filename"] == "clip.mp4"
    assert body["mime_type"] == "video/mp4"
    assert body["file_size"] == len(_MP4_BYTES)
    assert body["storage_path"]
    assert body["ingestion_status"] == "completed"
    assert body["organization_id"] == org_id
    # no frame/transcript extraction: title falls back to filename, content is empty
    assert body["title"] == "clip.mp4"
    assert body["content"] == ""


def test_title_override(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/video",
        data={"organization_id": str(org_id), "title": "Site Walkthrough"},
        files={"file": ("video_001.webm", b"fake webm bytes", "video/webm")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Site Walkthrough"
    assert body["content"] == ""


def test_metadata_persists_and_is_retrievable(client, org_id):
    content = b"fake quicktime bytes"

    create_resp = client.post(
        "/api/v1/knowledge/ingest/video",
        data={"organization_id": str(org_id)},
        files={"file": ("presentation.mov", content, "video/quicktime")},
    )
    assert create_resp.status_code == 201
    document_id = create_resp.json()["id"]

    list_resp = client.get(f"/api/v1/knowledge/organization/{org_id}")
    assert list_resp.status_code == 200
    stored = next(d for d in list_resp.json() if d["id"] == document_id)

    assert stored["source_type"] == "video"
    assert stored["original_filename"] == "presentation.mov"
    assert stored["mime_type"] == "video/quicktime"
    assert stored["file_size"] == len(content)
    assert stored["storage_path"]
    assert stored["ingestion_status"] == "completed"
    assert stored["title"] == "presentation.mov"
    assert stored["content"] == ""


def test_all_supported_mime_types_are_accepted(client, org_id):
    supported = [
        ("a.mp4", "video/mp4"),
        ("b.webm", "video/webm"),
        ("c.mov", "video/quicktime"),
        ("d.avi", "video/x-msvideo"),
        ("e.mpeg", "video/mpeg"),
    ]
    for filename, mime_type in supported:
        response = client.post(
            "/api/v1/knowledge/ingest/video",
            data={"organization_id": str(org_id)},
            files={"file": (filename, b"bytes", mime_type)},
        )
        assert response.status_code == 201, f"{mime_type} should be accepted"
        assert response.json()["mime_type"] == mime_type


def test_unsupported_mime_type_is_rejected(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/video",
        data={"organization_id": str(org_id)},
        files={"file": ("audio.mp3", b"fake mp3 bytes", "audio/mpeg")},
    )

    assert response.status_code == 415


def test_oversized_upload_is_rejected(client, org_id):
    max_size = get_settings().max_upload_size_bytes
    oversized_content = b"x" * (max_size + 1024)

    response = client.post(
        "/api/v1/knowledge/ingest/video",
        data={"organization_id": str(org_id)},
        files={"file": ("huge.mp4", oversized_content, "video/mp4")},
    )

    assert response.status_code == 413

    # nothing was persisted for the rejected upload
    list_resp = client.get(f"/api/v1/knowledge/organization/{org_id}")
    assert list_resp.json() == []
