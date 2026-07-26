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


def test_create_conversation_success(client, org_id, token):
    response = client.post(
        "/api/v1/conversations", json={"title": "Support chat"}, headers=_headers(token)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Support chat"
    assert body["status"] == "active"
    assert body["organization_id"] == org_id


def test_create_conversation_without_title(client, org_id, token):
    response = client.post("/api/v1/conversations", json={}, headers=_headers(token))

    assert response.status_code == 201
    assert response.json()["title"] is None


def test_create_conversation_requires_authentication(client, org_id):
    response = client.post("/api/v1/conversations", json={"title": "No token"})

    assert response.status_code == 401


def test_create_conversation_rejects_invalid_body_type(client, org_id, token):
    response = client.post(
        "/api/v1/conversations", json={"title": 12345}, headers=_headers(token)
    )

    assert response.status_code == 422


# --- list / pagination --------------------------------------------------------


def test_list_conversations_scoped_to_organization(client, org_id, token, other_org_id, other_token):
    client.post("/api/v1/conversations", json={"title": "Org A"}, headers=_headers(token))
    client.post("/api/v1/conversations", json={"title": "Org B"}, headers=_headers(other_token))

    org_a_response = client.get("/api/v1/conversations", headers=_headers(token))
    org_b_response = client.get("/api/v1/conversations", headers=_headers(other_token))

    assert len(org_a_response.json()) == 1
    assert org_a_response.json()[0]["title"] == "Org A"
    assert len(org_b_response.json()) == 1
    assert org_b_response.json()[0]["title"] == "Org B"


def test_list_conversations_requires_authentication(client, org_id):
    response = client.get("/api/v1/conversations")

    assert response.status_code == 401


def test_list_conversations_pagination(client, org_id, token):
    for i in range(5):
        client.post("/api/v1/conversations", json={"title": f"Conversation {i}"}, headers=_headers(token))

    first_page = client.get(
        "/api/v1/conversations", params={"skip": 0, "limit": 2}, headers=_headers(token)
    )
    second_page = client.get(
        "/api/v1/conversations", params={"skip": 2, "limit": 2}, headers=_headers(token)
    )

    assert len(first_page.json()) == 2
    assert len(second_page.json()) == 2
    assert {c["id"] for c in first_page.json()}.isdisjoint({c["id"] for c in second_page.json()})


def test_list_conversations_rejects_negative_skip(client, org_id, token):
    response = client.get("/api/v1/conversations", params={"skip": -1}, headers=_headers(token))

    assert response.status_code == 422


def test_list_conversations_rejects_excessive_limit(client, org_id, token):
    response = client.get("/api/v1/conversations", params={"limit": 101}, headers=_headers(token))

    assert response.status_code == 422


# --- get ----------------------------------------------------------------------


def test_get_conversation_success(client, org_id, token):
    created = client.post(
        "/api/v1/conversations", json={"title": "Findable"}, headers=_headers(token)
    ).json()

    response = client.get(f"/api/v1/conversations/{created['id']}", headers=_headers(token))

    assert response.status_code == 200
    assert response.json()["title"] == "Findable"


def test_get_conversation_not_found(client, org_id, token):
    response = client.get("/api/v1/conversations/999999", headers=_headers(token))

    assert response.status_code == 404


def test_get_conversation_cross_tenant_returns_not_found(client, org_id, token, other_token):
    created = client.post(
        "/api/v1/conversations", json={"title": "Org A's private conversation"}, headers=_headers(token)
    ).json()

    response = client.get(f"/api/v1/conversations/{created['id']}", headers=_headers(other_token))

    assert response.status_code == 404


# --- archive flow ----------------------------------------------------------------


def test_archive_conversation_success(client, org_id, token):
    created = client.post(
        "/api/v1/conversations", json={"title": "To be archived"}, headers=_headers(token)
    ).json()

    response = client.patch(f"/api/v1/conversations/{created['id']}/archive", headers=_headers(token))

    assert response.status_code == 200
    assert response.json()["status"] == "archived"

    # confirm persisted, not just returned
    fetched = client.get(f"/api/v1/conversations/{created['id']}", headers=_headers(token))
    assert fetched.json()["status"] == "archived"


def test_archive_conversation_not_found(client, org_id, token):
    response = client.patch("/api/v1/conversations/999999/archive", headers=_headers(token))

    assert response.status_code == 404


def test_archive_conversation_cross_tenant_returns_not_found(client, org_id, token, other_token):
    created = client.post(
        "/api/v1/conversations", json={"title": "Org A conversation"}, headers=_headers(token)
    ).json()

    response = client.patch(f"/api/v1/conversations/{created['id']}/archive", headers=_headers(other_token))

    assert response.status_code == 404
    # confirm the conversation's status was left untouched
    fetched = client.get(f"/api/v1/conversations/{created['id']}", headers=_headers(token))
    assert fetched.json()["status"] == "active"


# --- delete ----------------------------------------------------------------------


def test_delete_conversation_success(client, org_id, token):
    created = client.post(
        "/api/v1/conversations", json={"title": "Temporary"}, headers=_headers(token)
    ).json()

    response = client.delete(f"/api/v1/conversations/{created['id']}", headers=_headers(token))

    assert response.status_code == 204
    assert client.get(f"/api/v1/conversations/{created['id']}", headers=_headers(token)).status_code == 404


def test_delete_conversation_not_found(client, org_id, token):
    response = client.delete("/api/v1/conversations/999999", headers=_headers(token))

    assert response.status_code == 404


def test_delete_conversation_cross_tenant_returns_not_found(client, org_id, token, other_token):
    created = client.post(
        "/api/v1/conversations", json={"title": "Org A conversation"}, headers=_headers(token)
    ).json()

    response = client.delete(f"/api/v1/conversations/{created['id']}", headers=_headers(other_token))

    assert response.status_code == 404
    assert client.get(f"/api/v1/conversations/{created['id']}", headers=_headers(token)).status_code == 200
