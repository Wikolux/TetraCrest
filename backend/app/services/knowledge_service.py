from sqlalchemy.orm import Session

from app.models.knowledge_document import KnowledgeDocument
from app.repositories.knowledge_document_repository import KnowledgeDocumentRepository
from database import SessionLocal


class KnowledgeService:
    def __init__(self, db: Session | None = None):
        self.db = db or SessionLocal()
        self.repo = KnowledgeDocumentRepository(self.db)

    def create(self, title: str, content: str, organization_id: int, created_by: int | None = None) -> KnowledgeDocument:
        doc = KnowledgeDocument(title=title, content=content, organization_id=organization_id, created_by=created_by)
        return self.repo.create(doc)

    def list_for_organization(self, organization_id: int):
        return self.repo.get_by_organization(organization_id)
