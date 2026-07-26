from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.repositories.conversation_repository import ConversationRepository
from database import SessionLocal


class ConversationService:
    def __init__(self, db: Session | None = None):
        self.db = db or SessionLocal()
        self.repo = ConversationRepository(self.db)

    def create_conversation(
        self,
        organization_id: int,
        user_id: int | None = None,
        title: str | None = None,
    ) -> Conversation:
        conversation = Conversation(
            organization_id=organization_id,
            user_id=user_id,
            title=title,
        )
        return self.repo.create(conversation)

    def get_conversation(self, conversation_id: int, organization_id: int) -> Conversation | None:
        return self.repo.get_by_id_for_organization(conversation_id, organization_id)

    def list_conversations(self, organization_id: int, skip: int = 0, limit: int = 20):
        return self.repo.get_by_organization(organization_id, skip=skip, limit=limit)

    def list_active_conversations(self, organization_id: int, skip: int = 0, limit: int = 20):
        return self.repo.get_active_conversations(organization_id, skip=skip, limit=limit)

    def archive_conversation(self, conversation_id: int, organization_id: int) -> Conversation | None:
        conversation = self.repo.get_by_id_for_organization(conversation_id, organization_id)
        if not conversation:
            return None
        return self.repo.update(conversation, status="archived")

    def delete_conversation(self, conversation_id: int, organization_id: int) -> bool:
        conversation = self.repo.get_by_id_for_organization(conversation_id, organization_id)
        if not conversation:
            return False
        self.repo.delete(conversation)
        return True
