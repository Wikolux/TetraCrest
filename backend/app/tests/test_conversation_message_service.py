import pytest

from app.services.conversation_message_service import ConversationMessageService
from app.services.conversation_service import ConversationService
from app.services.embedding.base_provider import EmbeddingProviderError
from app.services.vector_store.base_store import VectorStoreError
from app.services.vector_store.types import VectorMetadata
from settings import get_settings


class _FakeEmbeddingPersistenceService:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[dict] = []

    def generate_and_store(self, vector_id, text, metadata=None):
        self.calls.append({"vector_id": vector_id, "text": text, "metadata": metadata})
        if self.error:
            raise self.error
        return [0.1, 0.2, 0.3]


@pytest.fixture()
def other_org_id(client):
    response = client.post("/api/v1/organizations", json={"name": "Other Org", "slug": "other-org"})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture()
def conversation_id(db_session, org_id):
    conversation = ConversationService(db_session).create_conversation(
        organization_id=org_id, title="Test conversation"
    )
    return conversation.id


@pytest.fixture()
def other_conversation_id(db_session, other_org_id):
    conversation = ConversationService(db_session).create_conversation(
        organization_id=other_org_id, title="Other org's conversation"
    )
    return conversation.id


# --- add_message ---------------------------------------------------------


def test_add_message_persists_fields(db_session, org_id, conversation_id):
    service = ConversationMessageService(db_session)

    message = service.add_message(conversation_id, org_id, content="Hello there", role="user")

    assert message is not None
    assert message.id is not None
    assert message.conversation_id == conversation_id
    assert message.organization_id == org_id
    assert message.role == "user"
    assert message.content == "Hello there"


def test_add_message_defaults_role_to_user(db_session, org_id, conversation_id):
    service = ConversationMessageService(db_session)

    message = service.add_message(conversation_id, org_id, content="Default role")

    assert message.role == "user"


def test_add_message_supports_assistant_role(db_session, org_id, conversation_id):
    service = ConversationMessageService(db_session)

    message = service.add_message(conversation_id, org_id, content="A reply", role="assistant")

    assert message.role == "assistant"


def test_add_message_returns_none_for_nonexistent_conversation(db_session, org_id):
    service = ConversationMessageService(db_session)

    assert service.add_message(999999, org_id, content="x") is None


def test_add_message_returns_none_for_cross_tenant_conversation(
    db_session, org_id, other_conversation_id
):
    service = ConversationMessageService(db_session)

    result = service.add_message(other_conversation_id, org_id, content="Hijack attempt")

    assert result is None


# --- get_message ----------------------------------------------------------


def test_get_message_returns_message_for_same_organization(db_session, org_id, conversation_id):
    service = ConversationMessageService(db_session)
    created = service.add_message(conversation_id, org_id, content="Findable")

    fetched = service.get_message(created.id, conversation_id, org_id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.content == "Findable"


def test_get_message_returns_none_for_nonexistent_message_id(db_session, org_id, conversation_id):
    service = ConversationMessageService(db_session)

    assert service.get_message(999999, conversation_id, org_id) is None


def test_get_message_returns_none_for_nonexistent_conversation(db_session, org_id, conversation_id):
    service = ConversationMessageService(db_session)
    created = service.add_message(conversation_id, org_id, content="Some message")

    assert service.get_message(created.id, 999999, org_id) is None


def test_get_message_returns_none_for_cross_tenant_conversation(
    db_session, org_id, conversation_id, other_org_id
):
    service = ConversationMessageService(db_session)
    created = service.add_message(conversation_id, org_id, content="Org A's message")

    assert service.get_message(created.id, conversation_id, other_org_id) is None


def test_get_message_returns_none_when_message_belongs_to_different_conversation(
    db_session, org_id, conversation_id
):
    service = ConversationMessageService(db_session)
    other_conversation = ConversationService(db_session).create_conversation(
        organization_id=org_id, title="A different conversation"
    )
    created = service.add_message(conversation_id, org_id, content="Belongs to conversation_id")

    # same org, valid message, but asked for it under the wrong conversation
    assert service.get_message(created.id, other_conversation.id, org_id) is None


# --- list_messages ---------------------------------------------------------


def test_list_messages_returns_messages_in_order(db_session, org_id, conversation_id):
    service = ConversationMessageService(db_session)
    service.add_message(conversation_id, org_id, content="first")
    service.add_message(conversation_id, org_id, content="second")
    service.add_message(conversation_id, org_id, content="third")

    messages = service.list_messages(conversation_id, org_id)

    assert [m.content for m in messages] == ["first", "second", "third"]


def test_list_messages_excludes_messages_from_other_conversations(db_session, org_id, conversation_id):
    service = ConversationMessageService(db_session)
    other_conversation = ConversationService(db_session).create_conversation(
        organization_id=org_id, title="Another conversation"
    )
    service.add_message(conversation_id, org_id, content="belongs here")
    service.add_message(other_conversation.id, org_id, content="belongs elsewhere")

    messages = service.list_messages(conversation_id, org_id)

    assert [m.content for m in messages] == ["belongs here"]


def test_list_messages_returns_empty_list_for_nonexistent_conversation(db_session, org_id):
    service = ConversationMessageService(db_session)

    assert service.list_messages(999999, org_id) == []


def test_list_messages_returns_empty_list_for_cross_tenant_conversation(
    db_session, org_id, conversation_id, other_org_id
):
    service = ConversationMessageService(db_session)
    service.add_message(conversation_id, org_id, content="Org A's message")

    assert service.list_messages(conversation_id, other_org_id) == []


def test_list_messages_pagination(db_session, org_id, conversation_id):
    service = ConversationMessageService(db_session)
    for i in range(5):
        service.add_message(conversation_id, org_id, content=f"message {i}")

    first_page = service.list_messages(conversation_id, org_id, skip=0, limit=2)
    second_page = service.list_messages(conversation_id, org_id, skip=2, limit=2)

    assert [m.content for m in first_page] == ["message 0", "message 1"]
    assert [m.content for m in second_page] == ["message 2", "message 3"]


# --- API surface -----------------------------------------------------------


def test_service_has_no_update_or_delete_methods(db_session):
    service = ConversationMessageService(db_session)

    assert not hasattr(service, "update_message")
    assert not hasattr(service, "delete_message")


# --- embedding persistence ---------------------------------------------------


def test_add_message_triggers_embedding_persistence_exactly_once(db_session, org_id, conversation_id):
    embedding_persistence = _FakeEmbeddingPersistenceService()
    service = ConversationMessageService(db_session, embedding_persistence_service=embedding_persistence)

    service.add_message(conversation_id, org_id, content="Hello there")

    assert len(embedding_persistence.calls) == 1


def test_add_message_uses_correct_vector_id_and_text(db_session, org_id, conversation_id):
    embedding_persistence = _FakeEmbeddingPersistenceService()
    service = ConversationMessageService(db_session, embedding_persistence_service=embedding_persistence)

    message = service.add_message(conversation_id, org_id, content="Hello there")

    call = embedding_persistence.calls[0]
    assert call["vector_id"] == f"conversation_message:{message.id}"
    assert call["text"] == "Hello there"


def test_add_message_uses_correct_metadata(db_session, org_id, conversation_id):
    embedding_persistence = _FakeEmbeddingPersistenceService()
    service = ConversationMessageService(db_session, embedding_persistence_service=embedding_persistence)

    message = service.add_message(conversation_id, org_id, content="Hello there")

    metadata = embedding_persistence.calls[0]["metadata"]
    assert isinstance(metadata, VectorMetadata)
    assert metadata.organization_id == org_id
    assert metadata.resource_type == "conversation_message"
    assert metadata.resource_id == message.id


def test_add_message_does_not_trigger_embedding_persistence_for_nonexistent_conversation(
    db_session, org_id
):
    embedding_persistence = _FakeEmbeddingPersistenceService()
    service = ConversationMessageService(db_session, embedding_persistence_service=embedding_persistence)

    result = service.add_message(999999, org_id, content="never saved")

    assert result is None
    assert len(embedding_persistence.calls) == 0


def test_add_message_succeeds_even_when_embedding_provider_fails(db_session, org_id, conversation_id):
    embedding_persistence = _FakeEmbeddingPersistenceService(error=EmbeddingProviderError("provider down"))
    service = ConversationMessageService(db_session, embedding_persistence_service=embedding_persistence)

    message = service.add_message(conversation_id, org_id, content="Still saved despite the failure.")

    assert message is not None
    assert service.get_message(message.id, conversation_id, org_id) is not None
    assert len(embedding_persistence.calls) == 1


def test_add_message_succeeds_even_when_vector_store_fails(db_session, org_id, conversation_id):
    embedding_persistence = _FakeEmbeddingPersistenceService(error=VectorStoreError("store down"))
    service = ConversationMessageService(db_session, embedding_persistence_service=embedding_persistence)

    message = service.add_message(conversation_id, org_id, content="Still saved despite the failure.")

    assert message is not None
    assert service.get_message(message.id, conversation_id, org_id) is not None
    assert len(embedding_persistence.calls) == 1


def test_conversation_message_service_falls_back_to_none_when_embedding_subsystem_unconfigured(
    db_session, monkeypatch
):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()

    try:
        service = ConversationMessageService(db_session)
        assert service.embedding_persistence_service is None
    finally:
        get_settings.cache_clear()
