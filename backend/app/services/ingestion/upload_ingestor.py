from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.knowledge_document import KnowledgeDocument
from app.services.classification_service import ClassificationService
from app.services.ingestion.base_ingestor import BaseIngestor
from app.services.storage_service import FileTooLargeError, StorageService

ALLOWED_UPLOAD_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class UploadIngestor(BaseIngestor):
    """Ingests a directly uploaded file.

    This is the existing POST /knowledge/ingest path, extracted unchanged
    from KnowledgeService.ingest_upload into the ingestion framework.
    """

    source_type = "upload"

    def __init__(self, db: Session, storage: StorageService | None = None):
        super().__init__(db)
        self.storage = storage or StorageService()

    def ingest(
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

        final_title = title or file.filename or "Untitled"
        final_content = content or ""
        classification = ClassificationService().classify(
            title=final_title,
            content=final_content,
            original_filename=file.filename,
            mime_type=file.content_type,
        )

        return self._persist(
            organization_id=organization_id,
            created_by=created_by,
            title=final_title,
            content=final_content,
            original_filename=file.filename,
            mime_type=file.content_type,
            file_size=file_size,
            storage_path=storage_path,
            ingestion_status="completed",
            classification=classification,
        )
