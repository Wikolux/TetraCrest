from settings import get_settings


def test_successful_upload(client, org_id):
    content = b"hello world, this is a test document"

    response = client.post(
        "/api/v1/knowledge/ingest",
        data={"organization_id": str(org_id), "title": "My Doc"},
        files={"file": ("notes.txt", content, "text/plain")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "My Doc"
    assert body["source_type"] == "upload"
    assert body["original_filename"] == "notes.txt"
    assert body["mime_type"] == "text/plain"
    assert body["file_size"] == len(content)
    assert body["storage_path"]
    assert body["ingestion_status"] == "completed"
    assert body["organization_id"] == org_id


def test_metadata_persists_and_is_retrievable(client, org_id):
    content = b"persisted content"

    create_resp = client.post(
        "/api/v1/knowledge/ingest",
        data={"organization_id": str(org_id)},
        files={"file": ("report.pdf", content, "application/pdf")},
    )
    assert create_resp.status_code == 201
    document_id = create_resp.json()["id"]

    list_resp = client.get(f"/api/v1/knowledge/organization/{org_id}")
    assert list_resp.status_code == 200
    stored = next(d for d in list_resp.json() if d["id"] == document_id)

    assert stored["source_type"] == "upload"
    assert stored["original_filename"] == "report.pdf"
    assert stored["mime_type"] == "application/pdf"
    assert stored["file_size"] == len(content)
    assert stored["storage_path"]
    assert stored["ingestion_status"] == "completed"
    # no title/content supplied: falls back to filename / empty content
    assert stored["title"] == "report.pdf"
    assert stored["content"] == ""


def test_unsupported_mime_type_is_rejected(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest",
        data={"organization_id": str(org_id)},
        files={"file": ("archive.zip", b"PK\x03\x04", "application/zip")},
    )

    assert response.status_code == 415


def test_oversized_upload_is_rejected(client, org_id):
    max_size = get_settings().max_upload_size_bytes
    oversized_content = b"x" * (max_size + 1024)

    response = client.post(
        "/api/v1/knowledge/ingest",
        data={"organization_id": str(org_id)},
        files={"file": ("big.txt", oversized_content, "text/plain")},
    )

    assert response.status_code == 413

    # nothing was persisted for the rejected upload
    list_resp = client.get(f"/api/v1/knowledge/organization/{org_id}")
    assert list_resp.json() == []
