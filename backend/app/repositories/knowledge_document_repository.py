from app.models.knowledge_document import KnowledgeDocument
from app.repositories.base import BaseRepository
from sqlalchemy.orm import Session


class KnowledgeDocumentRepository(BaseRepository[KnowledgeDocument]):
    def __init__(self, db: Session):
        super().__init__(KnowledgeDocument, db)

    def get_by_organization(self, organization_id: int, skip: int = 0, limit: int = 20):
        return (
            self.db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
