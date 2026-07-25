from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.knowledge_document import KnowledgeDocument
from app.services.ingestion.base_ingestor import BaseIngestor
from app.services.storage_service import FileTooLargeError, StorageService

ALLOWED_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}


class ImageIngestor(BaseIngestor):
    """Ingests an uploaded image.

    Stores the file only - no OCR, AI vision, caption generation, image
    description, object detection, or embeddings. Those are later phases;
    `content` is always empty here since nothing extracts text from the
    image yet.
    """

    source_type = "image"

    def __init__(self, db: Session, storage: StorageService | None = None):
        super().__init__(db)
        self.storage = storage or StorageService()

    def ingest(
        self,
        file: UploadFile,
        organization_id: int,
        created_by: int | None = None,
        title: str | None = None,
    ) -> KnowledgeDocument:
        if file.content_type not in ALLOWED_IMAGE_MIME_TYPES:
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

        return self._persist(
            organization_id=organization_id,
            created_by=created_by,
            title=title or file.filename or "Untitled",
            content="",
            original_filename=file.filename,
            mime_type=file.content_type,
            file_size=file_size,
            storage_path=storage_path,
            ingestion_status="completed",
        )
