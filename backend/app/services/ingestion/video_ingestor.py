from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.knowledge_document import KnowledgeDocument
from app.services.ingestion.base_ingestor import BaseIngestor
from app.services.storage_service import FileTooLargeError, StorageService

ALLOWED_VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-msvideo",
    "video/mpeg",
}


class VideoIngestor(BaseIngestor):
    """Ingests an uploaded video file.

    Stores the file only - no OCR, transcription, frame extraction,
    thumbnails, ffmpeg, or AI processing of any kind. Those are later
    phases; `content` is always empty here since nothing extracts anything
    from the video yet.
    """

    source_type = "video"

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
        if file.content_type not in ALLOWED_VIDEO_MIME_TYPES:
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
