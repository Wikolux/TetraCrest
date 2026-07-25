from settings import get_settings

_WAV_BYTES = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVEfake-audio-data"


def test_successful_upload(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/audio",
        data={"organization_id": str(org_id)},
        files={"file": ("recording.wav", _WAV_BYTES, "audio/wav")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "audio"
    assert body["original_filename"] == "recording.wav"
    assert body["mime_type"] == "audio/wav"
    assert body["file_size"] == len(_WAV_BYTES)
    assert body["storage_path"]
    assert body["ingestion_status"] == "completed"
    assert body["organization_id"] == org_id
    # no transcription: title falls back to filename, content is empty
    assert body["title"] == "recording.wav"
    assert body["content"] == ""


def test_title_override(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/audio",
        data={"organization_id": str(org_id), "title": "Interview Recording"},
        files={"file": ("audio_001.mp3", b"fake mp3 bytes", "audio/mpeg")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Interview Recording"
    assert body["content"] == ""


def test_metadata_persists_and_is_retrievable(client, org_id):
    content = b"fake ogg bytes"

    create_resp = client.post(
        "/api/v1/knowledge/ingest/audio",
        data={"organization_id": str(org_id)},
        files={"file": ("voice_note.ogg", content, "audio/ogg")},
    )
    assert create_resp.status_code == 201
    document_id = create_resp.json()["id"]

    list_resp = client.get(f"/api/v1/knowledge/organization/{org_id}")
    assert list_resp.status_code == 200
    stored = next(d for d in list_resp.json() if d["id"] == document_id)

    assert stored["source_type"] == "audio"
    assert stored["original_filename"] == "voice_note.ogg"
    assert stored["mime_type"] == "audio/ogg"
    assert stored["file_size"] == len(content)
    assert stored["storage_path"]
    assert stored["ingestion_status"] == "completed"
    assert stored["title"] == "voice_note.ogg"
    assert stored["content"] == ""


def test_all_supported_mime_types_are_accepted(client, org_id):
    supported = [
        ("a.mp3", "audio/mpeg"),
        ("b.mp3", "audio/mp3"),
        ("c.wav", "audio/wav"),
        ("d.wav", "audio/x-wav"),
        ("e.m4a", "audio/mp4"),
        ("f.m4a", "audio/x-m4a"),
        ("g.ogg", "audio/ogg"),
        ("h.webm", "audio/webm"),
    ]
    for filename, mime_type in supported:
        response = client.post(
            "/api/v1/knowledge/ingest/audio",
            data={"organization_id": str(org_id)},
            files={"file": (filename, b"bytes", mime_type)},
        )
        assert response.status_code == 201, f"{mime_type} should be accepted"
        assert response.json()["mime_type"] == mime_type


def test_unsupported_mime_type_is_rejected(client, org_id):
    response = client.post(
        "/api/v1/knowledge/ingest/audio",
        data={"organization_id": str(org_id)},
        files={"file": ("video.mp4", b"fake video bytes", "video/mp4")},
    )

    assert response.status_code == 415


def test_oversized_upload_is_rejected(client, org_id):
    max_size = get_settings().max_upload_size_bytes
    oversized_content = b"x" * (max_size + 1024)

    response = client.post(
        "/api/v1/knowledge/ingest/audio",
        data={"organization_id": str(org_id)},
        files={"file": ("huge.wav", oversized_content, "audio/wav")},
    )

    assert response.status_code == 413

    # nothing was persisted for the rejected upload
    list_resp = client.get(f"/api/v1/knowledge/organization/{org_id}")
    assert list_resp.json() == []
