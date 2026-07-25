from app.models.conversation import Conversation
from app.repositories.base import BaseRepository
from sqlalchemy.orm import Session


class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self, db: Session):
        super().__init__(Conversation, db)

    def get_by_organization(self, organization_id: int, skip: int = 0, limit: int = 20):
        return (
            self.db.query(Conversation)
            .filter(Conversation.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_active_conversations(self, organization_id: int, skip: int = 0, limit: int = 20):
        return (
            self.db.query(Conversation)
            .filter(
                Conversation.organization_id == organization_id,
                Conversation.status == "active",
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
