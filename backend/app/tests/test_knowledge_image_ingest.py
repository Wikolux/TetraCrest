from settings import get_settings

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-png-data"


def test_successful_upload(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/image",
        data={"organization_id": str(org_id)},
        files={"file": ("photo.png", _PNG_BYTES, "image/png")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "image"
    assert body["original_filename"] == "photo.png"
    assert body["mime_type"] == "image/png"
    assert body["file_size"] == len(_PNG_BYTES)
    assert body["storage_path"]
    assert body["ingestion_status"] == "completed"
    assert body["organization_id"] == org_id
    # no OCR/vision processing: title falls back to filename, content is empty
    assert body["title"] == "photo.png"
    assert body["content"] == ""


def test_title_override(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/image",
        data={"organization_id": str(org_id), "title": "Vacation Photo"},
        files={"file": ("img_0001.jpg", b"\xff\xd8\xff fake jpeg", "image/jpeg")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Vacation Photo"
    assert body["content"] == ""


def test_metadata_persists_and_is_retrievable(client, org_id):
    content = b"fake webp bytes"

    create_resp = client.post(
        "/api/v1/knowledge/ingest/image",
        data={"organization_id": str(org_id)},
        files={"file": ("banner.webp", content, "image/webp")},
    )
    assert create_resp.status_code == 201
    document_id = create_resp.json()["id"]

    list_resp = client.get(f"/api/v1/knowledge/organization/{org_id}")
    assert list_resp.status_code == 200
    stored = next(d for d in list_resp.json() if d["id"] == document_id)

    assert stored["source_type"] == "image"
    assert stored["original_filename"] == "banner.webp"
    assert stored["mime_type"] == "image/webp"
    assert stored["file_size"] == len(content)
    assert stored["storage_path"]
    assert stored["ingestion_status"] == "completed"
    assert stored["title"] == "banner.webp"
    assert stored["content"] == ""


def test_all_supported_mime_types_are_accepted(client, org_id):
    supported = [
        ("a.png", "image/png"),
        ("b.jpeg", "image/jpeg"),
        ("c.jpg", "image/jpg"),
        ("d.webp", "image/webp"),
        ("e.gif", "image/gif"),
    ]
    for filename, mime_type in supported:
        response = client.post(
            "/api/v1/knowledge/ingest/image",
            data={"organization_id": str(org_id)},
            files={"file": (filename, b"bytes", mime_type)},
        )
        assert response.status_code == 201, f"{mime_type} should be accepted"
        assert response.json()["mime_type"] == mime_type


def test_unsupported_mime_type_is_rejected(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/image",
        data={"organization_id": str(org_id)},
        files={"file": ("document.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 415


def test_oversized_upload_is_rejected(client, org_id):
    max_size = get_settings().max_upload_size_bytes
    oversized_content = b"x" * (max_size + 1024)

    response = client.post(
        "/api/v1/knowledge/ingest/image",
        data={"organization_id": str(org_id)},
        files={"file": ("huge.png", oversized_content, "image/png")},
    )

    assert response.status_code == 413

    # nothing was persisted for the rejected upload
    list_resp = client.get(f"/api/v1/knowledge/organization/{org_id}")
    assert list_resp.json() == []
