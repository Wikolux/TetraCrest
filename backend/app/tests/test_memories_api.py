import pytest


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def other_org_id(client):
    response = client.post("/api/v1/organizations", json={"name": "Other Org", "slug": "other-org"})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture()
def token(make_user, org_id):
    return make_user("alice", org_id)


@pytest.fixture()
def other_token(make_user, other_org_id):
    return make_user("bob", other_org_id)


# --- create -----------------------------------------------------------------


def test_create_memory_success(client, org_id, token):
    response = client.post(
        "/api/v1/memories",
        json={"content": "The user prefers dark mode.", "memory_type": "preference", "title": "UI"},
        headers=_headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["content"] == "The user prefers dark mode."
    assert body["memory_type"] == "preference"
    assert body["title"] == "UI"
    assert body["organization_id"] == org_id


def test_create_memory_defaults(client, org_id, token):
    response = client.post(
        "/api/v1/memories", json={"content": "A generic memory."}, headers=_headers(token)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["memory_type"] == "general"
    assert body["title"] is None


def test_create_memory_requires_authentication(client, org_id):
    response = client.post("/api/v1/memories", json={"content": "No token"})

    assert response.status_code == 401


def test_create_memory_missing_content_is_rejected(client, org_id, token):
    response = client.post("/api/v1/memories", json={}, headers=_headers(token))

    assert response.status_code == 422


# --- list / pagination --------------------------------------------------------


def test_list_memories_scoped_to_organization(client, org_id, token, other_org_id, other_token):
    client.post("/api/v1/memories", json={"content": "Org A memory"}, headers=_headers(token))
    client.post("/api/v1/memories", json={"content": "Org B memory"}, headers=_headers(other_token))

    org_a_response = client.get("/api/v1/memories", headers=_headers(token))
    org_b_response = client.get("/api/v1/memories", headers=_headers(other_token))

    assert org_a_response.status_code == 200
    assert len(org_a_response.json()) == 1
    assert org_a_response.json()[0]["content"] == "Org A memory"
    assert len(org_b_response.json()) == 1
    assert org_b_response.json()[0]["content"] == "Org B memory"


def test_list_memories_requires_authentication(client, org_id):
    response = client.get("/api/v1/memories")

    assert response.status_code == 401


def test_list_memories_pagination(client, org_id, token):
    for i in range(5):
        client.post("/api/v1/memories", json={"content": f"memory {i}"}, headers=_headers(token))

    first_page = client.get("/api/v1/memories", params={"skip": 0, "limit": 2}, headers=_headers(token))
    second_page = client.get("/api/v1/memories", params={"skip": 2, "limit": 2}, headers=_headers(token))

    assert len(first_page.json()) == 2
    assert len(second_page.json()) == 2
    first_ids = {m["id"] for m in first_page.json()}
    second_ids = {m["id"] for m in second_page.json()}
    assert first_ids.isdisjoint(second_ids)


def test_list_memories_rejects_negative_skip(client, org_id, token):
    response = client.get("/api/v1/memories", params={"skip": -1}, headers=_headers(token))

    assert response.status_code == 422


def test_list_memories_rejects_excessive_limit(client, org_id, token):
    response = client.get("/api/v1/memories", params={"limit": 101}, headers=_headers(token))

    assert response.status_code == 422


# --- get ----------------------------------------------------------------------


def test_get_memory_success(client, org_id, token):
    created = client.post(
        "/api/v1/memories", json={"content": "Findable"}, headers=_headers(token)
    ).json()

    response = client.get(f"/api/v1/memories/{created['id']}", headers=_headers(token))

    assert response.status_code == 200
    assert response.json()["content"] == "Findable"


def test_get_memory_not_found(client, org_id, token):
    response = client.get("/api/v1/memories/999999", headers=_headers(token))

    assert response.status_code == 404


def test_get_memory_cross_tenant_returns_not_found(client, org_id, token, other_token):
    created = client.post(
        "/api/v1/memories", json={"content": "Org A's private memory"}, headers=_headers(token)
    ).json()

    response = client.get(f"/api/v1/memories/{created['id']}", headers=_headers(other_token))

    assert response.status_code == 404


# --- update (PUT) ---------------------------------------------------------------


def test_update_memory_success(client, org_id, token):
    created = client.post(
        "/api/v1/memories", json={"content": "Original", "title": "Original title"}, headers=_headers(token)
    ).json()

    response = client.put(
        f"/api/v1/memories/{created['id']}",
        json={"content": "Updated", "title": "Updated title"},
        headers=_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "Updated"
    assert body["title"] == "Updated title"


def test_update_memory_not_found(client, org_id, token):
    response = client.put("/api/v1/memories/999999", json={"content": "x"}, headers=_headers(token))

    assert response.status_code == 404


def test_update_memory_cross_tenant_returns_not_found(client, org_id, token, other_token):
    created = client.post(
        "/api/v1/memories", json={"content": "Org A memory"}, headers=_headers(token)
    ).json()

    response = client.put(
        f"/api/v1/memories/{created['id']}", json={"content": "Hijacked"}, headers=_headers(other_token)
    )

    assert response.status_code == 404
    # confirm the original memory is untouched
    unaffected = client.get(f"/api/v1/memories/{created['id']}", headers=_headers(token))
    assert unaffected.json()["content"] == "Org A memory"


# --- delete ----------------------------------------------------------------------


def test_delete_memory_success(client, org_id, token):
    created = client.post(
        "/api/v1/memories", json={"content": "Temporary"}, headers=_headers(token)
    ).json()

    response = client.delete(f"/api/v1/memories/{created['id']}", headers=_headers(token))

    assert response.status_code == 204
    assert client.get(f"/api/v1/memories/{created['id']}", headers=_headers(token)).status_code == 404


def test_delete_memory_not_found(client, org_id, token):
    response = client.delete("/api/v1/memories/999999", headers=_headers(token))

    assert response.status_code == 404


def test_delete_memory_cross_tenant_returns_not_found(client, org_id, token, other_token):
    created = client.post(
        "/api/v1/memories", json={"content": "Org A memory"}, headers=_headers(token)
    ).json()

    response = client.delete(f"/api/v1/memories/{created['id']}", headers=_headers(other_token))

    assert response.status_code == 404
    # confirm the memory still exists
    assert client.get(f"/api/v1/memories/{created['id']}", headers=_headers(token)).status_code == 200
