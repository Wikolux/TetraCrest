from app.core.constants import (
    RESOURCE_CONVERSATION_MESSAGE,
    RESOURCE_KNOWLEDGE,
    RESOURCE_MEMORY,
)

_SEPARATOR = ":"


class VectorId:
    """Single source of truth for constructing VectorStore identifiers.

    Every resource type that will eventually get an embedding persisted
    (Memory, ConversationMessage, KnowledgeDocument, ...) builds its
    VectorStore key through this helper instead of hand-rolling an
    f-string at each call site, so the id format only has one place to
    change.

    Not wired into any service yet - that's M13.8's job.
    """

    @staticmethod
    def memory(memory_id: int) -> str:
        return f"{RESOURCE_MEMORY}{_SEPARATOR}{memory_id}"

    @staticmethod
    def conversation_message(message_id: int) -> str:
        return f"{RESOURCE_CONVERSATION_MESSAGE}{_SEPARATOR}{message_id}"

    @staticmethod
    def knowledge(document_id: int) -> str:
        return f"{RESOURCE_KNOWLEDGE}{_SEPARATOR}{document_id}"
