from sqlalchemy.orm import Session

from app.core.enums import ResourceType
from app.logging_utils import get_logger
from app.models.conversation_message import ConversationMessage
from app.repositories.conversation_message_repository import ConversationMessageRepository
from app.repositories.conversation_repository import ConversationRepository
from app.services.embedding.base_provider import EmbeddingProviderError
from app.services.embedding_persistence_service import EmbeddingPersistenceService
from app.services.vector_store.base_store import VectorStoreError
from app.services.vector_store.types import VectorMetadata
from app.services.vector_store.vector_id import VectorId
from database import SessionLocal

logger = get_logger(__name__)


class ConversationMessageService:
    def __init__(
        self,
        db: Session | None = None,
        embedding_persistence_service: EmbeddingPersistenceService | None = None,
    ):
        self.db = db or SessionLocal()
        self.repo = ConversationMessageRepository(self.db)
        self.conversation_repo = ConversationRepository(self.db)
        self.embedding_persistence_service = (
            embedding_persistence_service or self._build_embedding_persistence_service()
        )

    @staticmethod
    def _build_embedding_persistence_service() -> EmbeddingPersistenceService | None:
        """Construct the default EmbeddingPersistenceService, degrading to None
        if the embedding subsystem is misconfigured (e.g. no API key yet).

        Message creation must work whether or not embeddings are configured -
        the same reasoning that makes NullVectorStore a safe default applies
        here: a missing/invalid embedding configuration should never stop
        the service itself from being usable.
        """
        try:
            return EmbeddingPersistenceService()
        except (EmbeddingProviderError, VectorStoreError):
            logger.error("embedding_persistence_service_unavailable", exc_info=True)
            return None

    def add_message(
        self,
        conversation_id: int,
        organization_id: int,
        content: str,
        role: str = "user",
    ) -> ConversationMessage | None:
        conversation = self.conversation_repo.get_by_id_for_organization(conversation_id, organization_id)
        if not conversation:
            return None

        message = ConversationMessage(
            organization_id=organization_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        message = self.repo.create(message)
        self._persist_embedding(message)
        return message

    def _persist_embedding(self, message: ConversationMessage) -> None:
        """Best-effort: the message row already exists by the time this runs,
        and any embedding failure here must never undo or block that.
        """
        if self.embedding_persistence_service is None:
            return
        try:
            self.embedding_persistence_service.generate_and_store(
                vector_id=VectorId.conversation_message(message.id),
                text=message.content,
                metadata=VectorMetadata(
                    organization_id=message.organization_id,
                    resource_type=ResourceType.CONVERSATION_MESSAGE,
                    resource_id=message.id,
                ),
            )
        except (EmbeddingProviderError, VectorStoreError) as exc:
            logger.error(
                "embedding_persistence_failed",
                extra={"resource_type": ResourceType.CONVERSATION_MESSAGE, "resource_id": message.id},
                exc_info=exc,
            )

    def get_message(
        self, message_id: int, conversation_id: int, organization_id: int
    ) -> ConversationMessage | None:
        conversation = self.conversation_repo.get_by_id_for_organization(conversation_id, organization_id)
        if not conversation:
            return None

        message = self.repo.get_by_id_for_organization(message_id, organization_id)
        if not message or message.conversation_id != conversation_id:
            return None
        return message

    def list_messages(
        self, conversation_id: int, organization_id: int, skip: int = 0, limit: int = 20
    ):
        conversation = self.conversation_repo.get_by_id_for_organization(conversation_id, organization_id)
        if not conversation:
            return []
        return self.repo.get_by_conversation(conversation_id, skip=skip, limit=limit)
