from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.knowledge_document import KnowledgeDocument
from app.repositories.knowledge_document_repository import KnowledgeDocumentRepository
from app.services.ingestion.upload_ingestor import UploadIngestor
from app.services.ingestion.url_ingestor import URLIngestor
from app.services.ingestion.youtube_ingestor import YouTubeIngestor
from app.services.storage_service import StorageService
from database import SessionLocal


class KnowledgeService:
    def __init__(self, db: Session | None = None, storage: StorageService | None = None):
        self.db = db or SessionLocal()
        self.repo = KnowledgeDocumentRepository(self.db)
        self.storage = storage or StorageService()

    def create(self, title: str, content: str, organization_id: int, created_by: int | None = None) -> KnowledgeDocument:
        doc = KnowledgeDocument(title=title, content=content, organization_id=organization_id, created_by=created_by)
        return self.repo.create(doc)

    def ingest_upload(
        self,
        file: UploadFile,
        organization_id: int,
        created_by: int | None = None,
        title: str | None = None,
        content: str | None = None,
    ) -> KnowledgeDocument:
        ingestor = UploadIngestor(self.db, storage=self.storage)
        return ingestor.ingest(
            file,
            organization_id,
            created_by=created_by,
            title=title,
            content=content,
        )

    def ingest_url(
        self,
        url: str,
        organization_id: int,
        created_by: int | None = None,
        title: str | None = None,
    ) -> KnowledgeDocument:
        ingestor = URLIngestor(self.db)
        return ingestor.ingest(url, organization_id, created_by=created_by, title=title)

    def ingest_youtube(
        self,
        video_url: str,
        organization_id: int,
        created_by: int | None = None,
        title: str | None = None,
    ) -> KnowledgeDocument:
        ingestor = YouTubeIngestor(self.db)
        return ingestor.ingest(video_url, organization_id, created_by=created_by, title=title)

    def list_for_organization(self, organization_id: int, skip: int = 0, limit: int = 20):
        return self.repo.get_by_organization(organization_id, skip=skip, limit=limit)

    def update(self, document_id: int, organization_id: int, **fields) -> KnowledgeDocument | None:
        document = self.repo.get_by_id_for_organization(document_id, organization_id)
        if not document:
            return None
        return self.repo.update(document, **fields)

    def delete(self, document_id: int, organization_id: int) -> bool:
        document = self.repo.get_by_id_for_organization(document_id, organization_id)
        if not document:
            return False
        self.repo.delete(document)
        return True
