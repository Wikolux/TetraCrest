from app.services.vector_store.vector_id import VectorId


def test_memory_vector_id_format():
    assert VectorId.memory(42) == "memory:42"


def test_conversation_message_vector_id_format():
    assert VectorId.conversation_message(7) == "conversation_message:7"


def test_knowledge_vector_id_format():
    assert VectorId.knowledge(3) == "knowledge:3"


def test_vector_ids_for_different_resources_never_collide():
    ids = {
        VectorId.memory(1),
        VectorId.conversation_message(1),
        VectorId.knowledge(1),
    }
    assert len(ids) == 3
