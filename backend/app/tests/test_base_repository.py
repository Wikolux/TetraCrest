import pytest

from app.models.memory import Memory
from app.repositories.memory_repository import MemoryRepository


@pytest.fixture()
def other_org_id(client):
    response = client.post("/api/v1/organizations", json={"name": "Other Org", "slug": "other-org"})
    assert response.status_code == 201
    return response.json()["id"]


def _create_memory(db_session, organization_id: int, content: str) -> Memory:
    memory = Memory(organization_id=organization_id, content=content, memory_type="general")
    db_session.add(memory)
    db_session.commit()
    db_session.refresh(memory)
    return memory


def test_get_many_for_organization_returns_matching_rows(db_session, org_id):
    repo = MemoryRepository(db_session)
    first = _create_memory(db_session, org_id, "first")
    second = _create_memory(db_session, org_id, "second")

    results = repo.get_many_for_organization([first.id, second.id], org_id)

    assert {r.id for r in results} == {first.id, second.id}


def test_get_many_for_organization_excludes_cross_tenant_rows(db_session, org_id, other_org_id):
    repo = MemoryRepository(db_session)
    mine = _create_memory(db_session, org_id, "mine")
    theirs = _create_memory(db_session, other_org_id, "theirs")

    results = repo.get_many_for_organization([mine.id, theirs.id], org_id)

    assert {r.id for r in results} == {mine.id}


def test_get_many_for_organization_silently_ignores_nonexistent_ids(db_session, org_id):
    repo = MemoryRepository(db_session)
    real = _create_memory(db_session, org_id, "real")

    results = repo.get_many_for_organization([real.id, 999999], org_id)

    assert {r.id for r in results} == {real.id}


def test_get_many_for_organization_returns_empty_list_for_empty_input(db_session, org_id):
    repo = MemoryRepository(db_session)

    assert repo.get_many_for_organization([], org_id) == []


def test_get_many_for_organization_returns_empty_list_when_nothing_matches(db_session, org_id, other_org_id):
    repo = MemoryRepository(db_session)
    theirs = _create_memory(db_session, other_org_id, "theirs")

    assert repo.get_many_for_organization([theirs.id], org_id) == []
