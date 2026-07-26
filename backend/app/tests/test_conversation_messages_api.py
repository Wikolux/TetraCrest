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


@pytest.fixture()
def conversation_id(client, token):
    response = client.post("/api/v1/conversations", json={"title": "Test conversation"}, headers=_headers(token))
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture()
def other_conversation_id(client, other_token):
    response = client.post(
        "/api/v1/conversations", json={"title": "Other org's conversation"}, headers=_headers(other_token)
    )
    assert response.status_code == 201
    return response.json()["id"]


# --- add_message --------------------------------------------------------------


def test_add_message_success(client, org_id, token, conversation_id):
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Hello there", "role": "user"},
        headers=_headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["content"] == "Hello there"
    assert body["role"] == "user"
    assert body["conversation_id"] == conversation_id
    assert body["organization_id"] == org_id


def test_add_message_defaults_role_to_user(client, org_id, token, conversation_id):
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Default role"},
        headers=_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["role"] == "user"


def test_add_message_supports_assistant_role(client, org_id, token, conversation_id):
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "A reply", "role": "assistant"},
        headers=_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["role"] == "assistant"


def test_add_message_rejects_invalid_role(client, org_id, token, conversation_id):
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Bad role", "role": "villain"},
        headers=_headers(token),
    )

    assert response.status_code == 422


def test_add_message_rejects_missing_content(client, org_id, token, conversation_id):
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"role": "user"},
        headers=_headers(token),
    )

    assert response.status_code == 422


def test_add_message_requires_authentication(client, org_id, conversation_id):
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages", json={"content": "No token"}
    )

    assert response.status_code == 401


def test_add_message_conversation_not_found(client, org_id, token):
    response = client.post(
        "/api/v1/conversations/999999/messages", json={"content": "x"}, headers=_headers(token)
    )

    assert response.status_code == 404


def test_add_message_cross_tenant_conversation_returns_not_found(
    client, org_id, token, other_conversation_id
):
    response = client.post(
        f"/api/v1/conversations/{other_conversation_id}/messages",
        json={"content": "Hijack attempt"},
        headers=_headers(token),
    )

    assert response.status_code == 404


# --- list_messages --------------------------------------------------------------


def test_list_messages_returns_in_chronological_order(client, org_id, token, conversation_id):
    for content in ["first", "second", "third"]:
        client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": content},
            headers=_headers(token),
        )

    response = client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=_headers(token))

    assert response.status_code == 200
    assert [m["content"] for m in response.json()] == ["first", "second", "third"]


def test_list_messages_pagination(client, org_id, token, conversation_id):
    for i in range(5):
        client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": f"message {i}"},
            headers=_headers(token),
        )

    first_page = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        params={"skip": 0, "limit": 2},
        headers=_headers(token),
    )
    second_page = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        params={"skip": 2, "limit": 2},
        headers=_headers(token),
    )

    assert [m["content"] for m in first_page.json()] == ["message 0", "message 1"]
    assert [m["content"] for m in second_page.json()] == ["message 2", "message 3"]


def test_list_messages_requires_authentication(client, org_id, conversation_id):
    response = client.get(f"/api/v1/conversations/{conversation_id}/messages")

    assert response.status_code == 401


def test_list_messages_returns_empty_for_nonexistent_conversation(client, org_id, token):
    response = client.get("/api/v1/conversations/999999/messages", headers=_headers(token))

    assert response.status_code == 200
    assert response.json() == []


def test_list_messages_returns_empty_for_cross_tenant_conversation(
    client, org_id, token, other_conversation_id, other_token
):
    client.post(
        f"/api/v1/conversations/{other_conversation_id}/messages",
        json={"content": "Org B's message"},
        headers=_headers(other_token),
    )

    response = client.get(
        f"/api/v1/conversations/{other_conversation_id}/messages", headers=_headers(token)
    )

    assert response.status_code == 200
    assert response.json() == []


# --- get_message --------------------------------------------------------------


def test_get_message_success(client, org_id, token, conversation_id):
    created = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Findable"},
        headers=_headers(token),
    ).json()

    response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages/{created['id']}", headers=_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["content"] == "Findable"


def test_get_message_not_found(client, org_id, token, conversation_id):
    response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages/999999", headers=_headers(token)
    )

    assert response.status_code == 404


def test_get_message_wrong_conversation_returns_not_found(client, org_id, token, conversation_id):
    other_conversation = client.post(
        "/api/v1/conversations", json={"title": "A different conversation"}, headers=_headers(token)
    ).json()
    created = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Belongs to conversation_id"},
        headers=_headers(token),
    ).json()

    response = client.get(
        f"/api/v1/conversations/{other_conversation['id']}/messages/{created['id']}",
        headers=_headers(token),
    )

    assert response.status_code == 404


def test_get_message_cross_tenant_returns_not_found(client, org_id, token, conversation_id, other_token):
    created = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Org A's message"},
        headers=_headers(token),
    ).json()

    response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages/{created['id']}", headers=_headers(other_token)
    )

    assert response.status_code == 404


def test_get_message_requires_authentication(client, org_id, token, conversation_id):
    created = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Needs auth"},
        headers=_headers(token),
    ).json()

    response = client.get(f"/api/v1/conversations/{conversation_id}/messages/{created['id']}")

    assert response.status_code == 401


# --- immutability ------------------------------------------------------------


def test_messages_have_no_update_endpoint(client, org_id, token, conversation_id):
    created = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Immutable"},
        headers=_headers(token),
    ).json()

    put_response = client.put(
        f"/api/v1/conversations/{conversation_id}/messages/{created['id']}",
        json={"content": "Edited"},
        headers=_headers(token),
    )
    patch_response = client.patch(
        f"/api/v1/conversations/{conversation_id}/messages/{created['id']}",
        json={"content": "Edited"},
        headers=_headers(token),
    )

    assert put_response.status_code == 405
    assert patch_response.status_code == 405


def test_messages_have_no_delete_endpoint(client, org_id, token, conversation_id):
    created = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Immutable"},
        headers=_headers(token),
    ).json()

    response = client.delete(
        f"/api/v1/conversations/{conversation_id}/messages/{created['id']}", headers=_headers(token)
    )

    assert response.status_code == 405
