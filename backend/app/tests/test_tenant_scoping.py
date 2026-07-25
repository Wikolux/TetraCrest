"""M11: mutate/delete must be tenant-scoped.

For each resource: create it under org_a, then verify a user from a different
tenant (org_b) cannot update or delete it (404, indistinguishable from a
resource that doesn't exist at all), while a user from its own tenant (org_a)
can.
"""


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _two_orgs(client):
    org_a = client.post(
        "/api/v1/organizations", json={"name": "Org A", "slug": "org-a"}
    ).json()["id"]
    org_b = client.post(
        "/api/v1/organizations", json={"name": "Org B", "slug": "org-b"}
    ).json()["id"]
    return org_a, org_b


def test_organization_cross_tenant_scoping(client, make_user):
    org_a, org_b = _two_orgs(client)
    token_a = make_user("alice", org_a)
    token_b = make_user("bob", org_b)

    cross_update = client.patch(
        f"/api/v1/organizations/{org_a}", json={"name": "Hijacked"}, headers=_headers(token_b)
    )
    assert cross_update.status_code == 404

    cross_delete = client.delete(f"/api/v1/organizations/{org_a}", headers=_headers(token_b))
    assert cross_delete.status_code == 404

    # org_a's data is untouched by org_b's attempts
    still_there = client.get(f"/api/v1/organizations/{org_a}")
    assert still_there.status_code == 200
    assert still_there.json()["name"] == "Org A"

    # a cross-tenant 404 is indistinguishable from a genuinely-nonexistent id
    nonexistent_404 = client.patch(
        "/api/v1/organizations/999999", json={"name": "x"}, headers=_headers(token_b)
    )
    assert nonexistent_404.status_code == cross_update.status_code == 404
    assert nonexistent_404.json() == cross_update.json()

    same_tenant_update = client.patch(
        f"/api/v1/organizations/{org_a}", json={"name": "Org A Renamed"}, headers=_headers(token_a)
    )
    assert same_tenant_update.status_code == 200
    assert same_tenant_update.json()["name"] == "Org A Renamed"

    same_tenant_delete = client.delete(f"/api/v1/organizations/{org_a}", headers=_headers(token_a))
    assert same_tenant_delete.status_code == 204


def test_project_cross_tenant_scoping(client, make_user):
    org_a, org_b = _two_orgs(client)
    token_a = make_user("alice", org_a)
    token_b = make_user("bob", org_b)
    project_id = client.post(
        "/api/v1/projects", json={"name": "Secret Project", "organization_id": org_a}
    ).json()["id"]

    cross_update = client.patch(
        f"/api/v1/projects/{project_id}", json={"status": "active"}, headers=_headers(token_b)
    )
    assert cross_update.status_code == 404

    cross_delete = client.delete(f"/api/v1/projects/{project_id}", headers=_headers(token_b))
    assert cross_delete.status_code == 404

    unaffected = client.get(f"/api/v1/projects/organization/{org_a}")
    assert any(p["id"] == project_id and p["status"] == "planning" for p in unaffected.json())

    same_tenant_update = client.patch(
        f"/api/v1/projects/{project_id}", json={"status": "active"}, headers=_headers(token_a)
    )
    assert same_tenant_update.status_code == 200
    assert same_tenant_update.json()["status"] == "active"

    same_tenant_delete = client.delete(f"/api/v1/projects/{project_id}", headers=_headers(token_a))
    assert same_tenant_delete.status_code == 204


def test_task_cross_tenant_scoping(client, make_user):
    org_a, org_b = _two_orgs(client)
    token_a = make_user("alice", org_a)
    token_b = make_user("bob", org_b)
    project_id = client.post(
        "/api/v1/projects", json={"name": "Rocket", "organization_id": org_a}
    ).json()["id"]
    task_id = client.post(
        "/api/v1/tasks",
        json={"title": "Secret Task", "organization_id": org_a, "project_id": project_id},
    ).json()["id"]

    cross_update = client.patch(
        f"/api/v1/tasks/{task_id}", json={"status": "done"}, headers=_headers(token_b)
    )
    assert cross_update.status_code == 404

    cross_delete = client.delete(f"/api/v1/tasks/{task_id}", headers=_headers(token_b))
    assert cross_delete.status_code == 404

    unaffected = client.get(f"/api/v1/tasks/project/{project_id}")
    assert any(t["id"] == task_id and t["status"] == "pending" for t in unaffected.json())

    same_tenant_update = client.patch(
        f"/api/v1/tasks/{task_id}", json={"status": "done"}, headers=_headers(token_a)
    )
    assert same_tenant_update.status_code == 200
    assert same_tenant_update.json()["status"] == "done"

    same_tenant_delete = client.delete(f"/api/v1/tasks/{task_id}", headers=_headers(token_a))
    assert same_tenant_delete.status_code == 204


def test_knowledge_document_cross_tenant_scoping(client, make_user):
    org_a, org_b = _two_orgs(client)
    token_a = make_user("alice", org_a)
    token_b = make_user("bob", org_b)
    document_id = client.post(
        "/api/v1/knowledge",
        json={"title": "Confidential", "content": "secret", "organization_id": org_a},
    ).json()["id"]

    cross_update = client.patch(
        f"/api/v1/knowledge/{document_id}",
        json={"content": "tampered"},
        headers=_headers(token_b),
    )
    assert cross_update.status_code == 404

    cross_delete = client.delete(f"/api/v1/knowledge/{document_id}", headers=_headers(token_b))
    assert cross_delete.status_code == 404

    unaffected = client.get(f"/api/v1/knowledge/organization/{org_a}")
    assert any(d["id"] == document_id and d["content"] == "secret" for d in unaffected.json())

    same_tenant_update = client.patch(
        f"/api/v1/knowledge/{document_id}",
        json={"content": "revised"},
        headers=_headers(token_a),
    )
    assert same_tenant_update.status_code == 200
    assert same_tenant_update.json()["content"] == "revised"

    same_tenant_delete = client.delete(f"/api/v1/knowledge/{document_id}", headers=_headers(token_a))
    assert same_tenant_delete.status_code == 204


def test_memory_record_cross_tenant_scoping(client, make_user):
    org_a, org_b = _two_orgs(client)
    token_a = make_user("alice", org_a)
    token_b = make_user("bob", org_b)
    record_id = client.post(
        "/api/v1/memory",
        json={"key": "secret-key", "value": "secret value", "organization_id": org_a},
    ).json()["id"]

    cross_update = client.patch(
        f"/api/v1/memory/{record_id}", json={"value": "tampered"}, headers=_headers(token_b)
    )
    assert cross_update.status_code == 404

    cross_delete = client.delete(f"/api/v1/memory/{record_id}", headers=_headers(token_b))
    assert cross_delete.status_code == 404

    unaffected = client.get(f"/api/v1/memory/organization/{org_a}")
    assert any(m["id"] == record_id and m["value"] == "secret value" for m in unaffected.json())

    same_tenant_update = client.patch(
        f"/api/v1/memory/{record_id}", json={"value": "revised"}, headers=_headers(token_a)
    )
    assert same_tenant_update.status_code == 200
    assert same_tenant_update.json()["value"] == "revised"

    same_tenant_delete = client.delete(f"/api/v1/memory/{record_id}", headers=_headers(token_a))
    assert same_tenant_delete.status_code == 204
