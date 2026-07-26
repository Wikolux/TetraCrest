from sqlalchemy.orm import Session

from app.models.conversation_message import ConversationMessage
from app.repositories.conversation_message_repository import ConversationMessageRepository
from app.repositories.conversation_repository import ConversationRepository
from database import SessionLocal


class ConversationMessageService:
    def __init__(self, db: Session | None = None):
        self.db = db or SessionLocal()
        self.repo = ConversationMessageRepository(self.db)
        self.conversation_repo = ConversationRepository(self.db)

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
        return self.repo.create(message)

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
