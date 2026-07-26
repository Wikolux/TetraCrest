import pytest

from app.services.conversation_service import ConversationService


@pytest.fixture()
def other_org_id(client):
    response = client.post("/api/v1/organizations", json={"name": "Other Org", "slug": "other-org"})
    assert response.status_code == 201
    return response.json()["id"]


def test_create_conversation_persists_fields(db_session, org_id):
    service = ConversationService(db_session)

    conversation = service.create_conversation(organization_id=org_id, title="Support chat")

    assert conversation.id is not None
    assert conversation.organization_id == org_id
    assert conversation.title == "Support chat"
    assert conversation.user_id is None


def test_create_conversation_defaults_to_active_status(db_session, org_id):
    service = ConversationService(db_session)

    conversation = service.create_conversation(organization_id=org_id)

    assert conversation.status == "active"
    assert conversation.title is None


def test_create_conversation_with_user_id(db_session, org_id):
    service = ConversationService(db_session)

    conversation = service.create_conversation(organization_id=org_id, user_id=7)

    assert conversation.user_id == 7


def test_get_conversation_returns_conversation_for_same_organization(db_session, org_id):
    service = ConversationService(db_session)
    created = service.create_conversation(organization_id=org_id, title="Findable")

    fetched = service.get_conversation(created.id, org_id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.title == "Findable"


def test_get_conversation_returns_none_for_nonexistent_id(db_session, org_id):
    service = ConversationService(db_session)

    assert service.get_conversation(999999, org_id) is None


def test_get_conversation_returns_none_for_cross_tenant_access(db_session, org_id, other_org_id):
    service = ConversationService(db_session)
    created = service.create_conversation(organization_id=org_id, title="Org A's private conversation")

    assert service.get_conversation(created.id, other_org_id) is None


def test_list_conversations_scoped_to_organization(db_session, org_id, other_org_id):
    service = ConversationService(db_session)
    service.create_conversation(organization_id=org_id, title="Org A 1")
    service.create_conversation(organization_id=org_id, title="Org A 2")
    service.create_conversation(organization_id=other_org_id, title="Org B 1")

    org_a_conversations = service.list_conversations(org_id)
    org_b_conversations = service.list_conversations(other_org_id)

    assert len(org_a_conversations) == 2
    assert len(org_b_conversations) == 1
    assert all(c.organization_id == org_id for c in org_a_conversations)


def test_list_conversations_pagination(db_session, org_id):
    service = ConversationService(db_session)
    for i in range(5):
        service.create_conversation(organization_id=org_id, title=f"Conversation {i}")

    first_page = service.list_conversations(org_id, skip=0, limit=2)
    second_page = service.list_conversations(org_id, skip=2, limit=2)

    assert len(first_page) == 2
    assert len(second_page) == 2
    assert {c.id for c in first_page}.isdisjoint({c.id for c in second_page})


def test_list_active_conversations_excludes_archived(db_session, org_id):
    service = ConversationService(db_session)
    active_one = service.create_conversation(organization_id=org_id, title="Active 1")
    active_two = service.create_conversation(organization_id=org_id, title="Active 2")
    to_archive = service.create_conversation(organization_id=org_id, title="Will be archived")
    service.archive_conversation(to_archive.id, org_id)

    active = service.list_active_conversations(org_id)

    assert {c.id for c in active} == {active_one.id, active_two.id}


def test_list_active_conversations_scoped_to_organization(db_session, org_id, other_org_id):
    service = ConversationService(db_session)
    service.create_conversation(organization_id=org_id, title="Org A active")
    service.create_conversation(organization_id=other_org_id, title="Org B active")

    org_a_active = service.list_active_conversations(org_id)

    assert len(org_a_active) == 1
    assert org_a_active[0].organization_id == org_id


def test_list_active_conversations_pagination(db_session, org_id):
    service = ConversationService(db_session)
    for i in range(5):
        service.create_conversation(organization_id=org_id, title=f"Active {i}")

    first_page = service.list_active_conversations(org_id, skip=0, limit=2)

    assert len(first_page) == 2


def test_archive_conversation_sets_status_to_archived(db_session, org_id):
    service = ConversationService(db_session)
    created = service.create_conversation(organization_id=org_id, title="To be archived")

    archived = service.archive_conversation(created.id, org_id)

    assert archived is not None
    assert archived.id == created.id
    assert archived.status == "archived"


def test_archive_conversation_returns_none_for_nonexistent_id(db_session, org_id):
    service = ConversationService(db_session)

    assert service.archive_conversation(999999, org_id) is None


def test_archive_conversation_returns_none_for_cross_tenant_access(db_session, org_id, other_org_id):
    service = ConversationService(db_session)
    created = service.create_conversation(organization_id=org_id, title="Org A conversation")

    result = service.archive_conversation(created.id, other_org_id)

    assert result is None
    # confirm the original conversation's status was left untouched
    untouched = service.get_conversation(created.id, org_id)
    assert untouched.status == "active"


def test_delete_conversation_deletes_for_same_organization(db_session, org_id):
    service = ConversationService(db_session)
    created = service.create_conversation(organization_id=org_id, title="Temporary")

    result = service.delete_conversation(created.id, org_id)

    assert result is True
    assert service.get_conversation(created.id, org_id) is None


def test_delete_conversation_returns_false_for_nonexistent_id(db_session, org_id):
    service = ConversationService(db_session)

    assert service.delete_conversation(999999, org_id) is False


def test_delete_conversation_returns_false_for_cross_tenant_access(db_session, org_id, other_org_id):
    service = ConversationService(db_session)
    created = service.create_conversation(organization_id=org_id, title="Org A conversation")

    result = service.delete_conversation(created.id, other_org_id)

    assert result is False
    # confirm the conversation still exists, untouched by the other tenant's attempt
    assert service.get_conversation(created.id, org_id) is not None


def test_conversation_service_has_no_generic_update_method(db_session):
    service = ConversationService(db_session)

    assert not hasattr(service, "update_conversation")


def test_conversation_service_has_no_message_related_methods(db_session):
    service = ConversationService(db_session)

    assert not hasattr(service, "add_message")
    assert not hasattr(service, "list_messages")
