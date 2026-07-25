from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.knowledge_document import KnowledgeDocument
from app.repositories.knowledge_document_repository import KnowledgeDocumentRepository
from app.services.storage_service import FileTooLargeError, StorageService
from database import SessionLocal

ALLOWED_UPLOAD_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


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
        if file.content_type not in ALLOWED_UPLOAD_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type: {file.content_type}",
            )

        try:
            storage_path, file_size = self.storage.save_upload(file, organization_id)
        except FileTooLargeError as exc:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
            ) from exc

        document = KnowledgeDocument(
            organization_id=organization_id,
            created_by=created_by,
            title=title or file.filename or "Untitled",
            content=content or "",
            source_type="upload",
            original_filename=file.filename,
            mime_type=file.content_type,
            file_size=file_size,
            storage_path=storage_path,
            ingestion_status="completed",
        )
        return self.repo.create(document)

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
