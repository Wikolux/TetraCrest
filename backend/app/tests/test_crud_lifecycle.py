"""CRUD lifecycle tests: create -> retrieve -> update -> verify -> delete -> verify 404.

Update and delete are tenant-scoped, so every mutation in these tests is made
by an authenticated user belonging to the resource's own organization.
"""


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_organization_crud_lifecycle(client, make_user):
    create_resp = client.post(
        "/api/v1/organizations",
        json={"name": "Acme", "slug": "acme", "description": "Test org"},
    )
    assert create_resp.status_code == 201
    org_id = create_resp.json()["id"]
    token = make_user("owner", org_id)

    retrieve_resp = client.get(f"/api/v1/organizations/{org_id}")
    assert retrieve_resp.status_code == 200
    assert retrieve_resp.json()["name"] == "Acme"

    update_resp = client.patch(
        f"/api/v1/organizations/{org_id}", json={"name": "Acme Corp"}, headers=_headers(token)
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Acme Corp"
    assert update_resp.json()["slug"] == "acme"  # untouched field preserved

    verify_resp = client.get(f"/api/v1/organizations/{org_id}")
    assert verify_resp.status_code == 200
    assert verify_resp.json()["name"] == "Acme Corp"

    delete_resp = client.delete(f"/api/v1/organizations/{org_id}", headers=_headers(token))
    assert delete_resp.status_code == 204
    assert delete_resp.content == b""

    verify_404 = client.get(f"/api/v1/organizations/{org_id}")
    assert verify_404.status_code == 404


def test_project_crud_lifecycle(client, org_id, make_user):
    token = make_user("owner", org_id)
    create_resp = client.post(
        "/api/v1/projects", json={"name": "Rocket", "organization_id": org_id}
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    retrieve_resp = client.get(f"/api/v1/projects/organization/{org_id}")
    assert retrieve_resp.status_code == 200
    assert any(p["id"] == project_id for p in retrieve_resp.json())

    update_resp = client.patch(
        f"/api/v1/projects/{project_id}", json={"status": "active"}, headers=_headers(token)
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "active"
    assert update_resp.json()["name"] == "Rocket"  # untouched field preserved

    verify_resp = client.get(f"/api/v1/projects/organization/{org_id}")
    updated = next(p for p in verify_resp.json() if p["id"] == project_id)
    assert updated["status"] == "active"

    delete_resp = client.delete(f"/api/v1/projects/{project_id}", headers=_headers(token))
    assert delete_resp.status_code == 204
    assert delete_resp.content == b""

    verify_404 = client.patch(
        f"/api/v1/projects/{project_id}", json={"status": "archived"}, headers=_headers(token)
    )
    assert verify_404.status_code == 404

    verify_delete_404 = client.delete(f"/api/v1/projects/{project_id}", headers=_headers(token))
    assert verify_delete_404.status_code == 404


def test_task_crud_lifecycle(client, org_id, project_id, make_user):
    token = make_user("owner", org_id)
    create_resp = client.post(
        "/api/v1/tasks",
        json={"title": "Write docs", "organization_id": org_id, "project_id": project_id},
    )
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]

    retrieve_resp = client.get(f"/api/v1/tasks/project/{project_id}")
    assert retrieve_resp.status_code == 200
    assert any(t["id"] == task_id for t in retrieve_resp.json())

    update_resp = client.patch(
        f"/api/v1/tasks/{task_id}", json={"status": "done"}, headers=_headers(token)
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "done"
    assert update_resp.json()["title"] == "Write docs"  # untouched field preserved

    verify_resp = client.get(f"/api/v1/tasks/project/{project_id}")
    updated = next(t for t in verify_resp.json() if t["id"] == task_id)
    assert updated["status"] == "done"

    delete_resp = client.delete(f"/api/v1/tasks/{task_id}", headers=_headers(token))
    assert delete_resp.status_code == 204
    assert delete_resp.content == b""

    verify_404 = client.patch(
        f"/api/v1/tasks/{task_id}", json={"status": "pending"}, headers=_headers(token)
    )
    assert verify_404.status_code == 404

    verify_delete_404 = client.delete(f"/api/v1/tasks/{task_id}", headers=_headers(token))
    assert verify_delete_404.status_code == 404


def test_knowledge_document_crud_lifecycle(client, org_id, make_user):
    token = make_user("owner", org_id)
    create_resp = client.post(
        "/api/v1/knowledge",
        json={"title": "Doc", "content": "original content", "organization_id": org_id},
    )
    assert create_resp.status_code == 201
    document_id = create_resp.json()["id"]

    retrieve_resp = client.get(f"/api/v1/knowledge/organization/{org_id}")
    assert retrieve_resp.status_code == 200
    assert any(d["id"] == document_id for d in retrieve_resp.json())

    update_resp = client.patch(
        f"/api/v1/knowledge/{document_id}",
        json={"content": "updated content"},
        headers=_headers(token),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["content"] == "updated content"
    assert update_resp.json()["title"] == "Doc"  # untouched field preserved

    verify_resp = client.get(f"/api/v1/knowledge/organization/{org_id}")
    updated = next(d for d in verify_resp.json() if d["id"] == document_id)
    assert updated["content"] == "updated content"

    delete_resp = client.delete(f"/api/v1/knowledge/{document_id}", headers=_headers(token))
    assert delete_resp.status_code == 204
    assert delete_resp.content == b""

    verify_404 = client.patch(
        f"/api/v1/knowledge/{document_id}", json={"content": "gone"}, headers=_headers(token)
    )
    assert verify_404.status_code == 404

    verify_delete_404 = client.delete(f"/api/v1/knowledge/{document_id}", headers=_headers(token))
    assert verify_delete_404.status_code == 404


def test_memory_record_crud_lifecycle(client, org_id, make_user):
    token = make_user("owner", org_id)
    create_resp = client.post(
        "/api/v1/memory",
        json={"key": "k1", "value": "original value", "organization_id": org_id},
    )
    assert create_resp.status_code == 201
    record_id = create_resp.json()["id"]

    retrieve_resp = client.get(f"/api/v1/memory/organization/{org_id}")
    assert retrieve_resp.status_code == 200
    assert any(m["id"] == record_id for m in retrieve_resp.json())

    update_resp = client.patch(
        f"/api/v1/memory/{record_id}", json={"value": "updated value"}, headers=_headers(token)
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["value"] == "updated value"
    assert update_resp.json()["key"] == "k1"  # untouched field preserved

    verify_resp = client.get(f"/api/v1/memory/organization/{org_id}")
    updated = next(m for m in verify_resp.json() if m["id"] == record_id)
    assert updated["value"] == "updated value"

    delete_resp = client.delete(f"/api/v1/memory/{record_id}", headers=_headers(token))
    assert delete_resp.status_code == 204
    assert delete_resp.content == b""

    verify_404 = client.patch(
        f"/api/v1/memory/{record_id}", json={"value": "gone"}, headers=_headers(token)
    )
    assert verify_404.status_code == 404

    verify_delete_404 = client.delete(f"/api/v1/memory/{record_id}", headers=_headers(token))
    assert verify_delete_404.status_code == 404


def test_update_nonexistent_resource_returns_404(client, org_id, make_user):
    token = make_user("owner", org_id)
    headers = _headers(token)
    assert client.patch("/api/v1/organizations/999999", json={"name": "x"}, headers=headers).status_code == 404
    assert client.patch("/api/v1/projects/999999", json={"name": "x"}, headers=headers).status_code == 404
    assert client.patch("/api/v1/tasks/999999", json={"title": "x"}, headers=headers).status_code == 404
    assert client.patch("/api/v1/knowledge/999999", json={"title": "x"}, headers=headers).status_code == 404
    assert client.patch("/api/v1/memory/999999", json={"key": "x"}, headers=headers).status_code == 404


def test_delete_nonexistent_resource_returns_404(client, org_id, make_user):
    token = make_user("owner", org_id)
    headers = _headers(token)
    assert client.delete("/api/v1/organizations/999999", headers=headers).status_code == 404
    assert client.delete("/api/v1/projects/999999", headers=headers).status_code == 404
    assert client.delete("/api/v1/tasks/999999", headers=headers).status_code == 404
    assert client.delete("/api/v1/knowledge/999999", headers=headers).status_code == 404
    assert client.delete("/api/v1/memory/999999", headers=headers).status_code == 404


def test_mutation_without_authentication_returns_401(client, org_id):
    assert client.patch(f"/api/v1/organizations/{org_id}", json={"name": "x"}).status_code == 401
    assert client.delete(f"/api/v1/organizations/{org_id}").status_code == 401
