from app.models.conversation_message import ConversationMessage
from app.repositories.base import BaseRepository
from sqlalchemy.orm import Session


class ConversationMessageRepository(BaseRepository[ConversationMessage]):
    def __init__(self, db: Session):
        super().__init__(ConversationMessage, db)

    def get_by_conversation(self, conversation_id: int, skip: int = 0, limit: int = 20):
        return (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at)
            .offset(skip)
            .limit(limit)
            .all()
        )
