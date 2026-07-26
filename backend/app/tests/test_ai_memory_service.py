import pytest

from app.services.ai_memory_service import AIMemoryService


@pytest.fixture()
def other_org_id(client):
    response = client.post("/api/v1/organizations", json={"name": "Other Org", "slug": "other-org"})
    assert response.status_code == 201
    return response.json()["id"]


def test_create_memory_persists_fields(db_session, org_id):
    service = AIMemoryService(db_session)

    memory = service.create_memory(
        organization_id=org_id,
        content="The user prefers dark mode.",
        memory_type="preference",
        title="UI Preference",
    )

    assert memory.id is not None
    assert memory.organization_id == org_id
    assert memory.memory_type == "preference"
    assert memory.title == "UI Preference"
    assert memory.content == "The user prefers dark mode."
    assert memory.user_id is None


def test_create_memory_defaults(db_session, org_id):
    service = AIMemoryService(db_session)

    memory = service.create_memory(organization_id=org_id, content="A generic memory.")

    assert memory.memory_type == "general"
    assert memory.title is None


def test_create_memory_with_user_id(db_session, org_id):
    service = AIMemoryService(db_session)

    memory = service.create_memory(organization_id=org_id, content="User-specific memory.", user_id=42)

    assert memory.user_id == 42


def test_get_memory_returns_memory_for_same_organization(db_session, org_id):
    service = AIMemoryService(db_session)
    created = service.create_memory(organization_id=org_id, content="Findable memory.")

    fetched = service.get_memory(created.id, org_id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.content == "Findable memory."


def test_get_memory_returns_none_for_nonexistent_id(db_session, org_id):
    service = AIMemoryService(db_session)

    assert service.get_memory(999999, org_id) is None


def test_get_memory_returns_none_for_cross_tenant_access(db_session, org_id, other_org_id):
    service = AIMemoryService(db_session)
    created = service.create_memory(organization_id=org_id, content="Org A's private memory.")

    assert service.get_memory(created.id, other_org_id) is None


def test_list_memories_scoped_to_organization(db_session, org_id, other_org_id):
    service = AIMemoryService(db_session)
    service.create_memory(organization_id=org_id, content="Org A memory 1")
    service.create_memory(organization_id=org_id, content="Org A memory 2")
    service.create_memory(organization_id=other_org_id, content="Org B memory")

    org_a_memories = service.list_memories(org_id)
    org_b_memories = service.list_memories(other_org_id)

    assert len(org_a_memories) == 2
    assert len(org_b_memories) == 1
    assert all(m.organization_id == org_id for m in org_a_memories)


def test_list_memories_pagination(db_session, org_id):
    service = AIMemoryService(db_session)
    for i in range(5):
        service.create_memory(organization_id=org_id, content=f"Memory {i}")

    first_page = service.list_memories(org_id, skip=0, limit=2)
    second_page = service.list_memories(org_id, skip=2, limit=2)

    assert len(first_page) == 2
    assert len(second_page) == 2
    assert {m.id for m in first_page}.isdisjoint({m.id for m in second_page})


def test_update_memory_updates_allowed_fields(db_session, org_id):
    service = AIMemoryService(db_session)
    created = service.create_memory(organization_id=org_id, content="Original content", title="Original")

    updated = service.update_memory(created.id, org_id, content="Updated content", title="Updated")

    assert updated is not None
    assert updated.content == "Updated content"
    assert updated.title == "Updated"
    assert updated.id == created.id


def test_update_memory_returns_none_for_nonexistent_id(db_session, org_id):
    service = AIMemoryService(db_session)

    assert service.update_memory(999999, org_id, content="x") is None


def test_update_memory_returns_none_for_cross_tenant_access(db_session, org_id, other_org_id):
    service = AIMemoryService(db_session)
    created = service.create_memory(organization_id=org_id, content="Org A memory")

    result = service.update_memory(created.id, other_org_id, content="Hijacked")

    assert result is None
    # confirm the original memory was left untouched
    untouched = service.get_memory(created.id, org_id)
    assert untouched.content == "Org A memory"


def test_delete_memory_deletes_for_same_organization(db_session, org_id):
    service = AIMemoryService(db_session)
    created = service.create_memory(organization_id=org_id, content="Temporary memory")

    result = service.delete_memory(created.id, org_id)

    assert result is True
    assert service.get_memory(created.id, org_id) is None


def test_delete_memory_returns_false_for_nonexistent_id(db_session, org_id):
    service = AIMemoryService(db_session)

    assert service.delete_memory(999999, org_id) is False


def test_delete_memory_returns_false_for_cross_tenant_access(db_session, org_id, other_org_id):
    service = AIMemoryService(db_session)
    created = service.create_memory(organization_id=org_id, content="Org A memory")

    result = service.delete_memory(created.id, other_org_id)

    assert result is False
    # confirm the memory still exists, untouched by the other tenant's attempt
    assert service.get_memory(created.id, org_id) is not None
