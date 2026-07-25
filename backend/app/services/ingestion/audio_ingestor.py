from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.knowledge_document import KnowledgeDocument
from app.services.classification_service import ClassificationService
from app.services.ingestion.base_ingestor import BaseIngestor
from app.services.storage_service import FileTooLargeError, StorageService

ALLOWED_AUDIO_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/x-m4a",
    "audio/ogg",
    "audio/webm",
}


class AudioIngestor(BaseIngestor):
    """Ingests an uploaded audio file.

    Stores the file only - no speech-to-text, Whisper, transcription, AI
    summarization, embeddings, speaker recognition, or language detection.
    Those are later phases; `content` is always empty here since nothing
    extracts text from the audio yet. Classification still runs against
    whatever signal is available (title, filename, mime type), via the
    shared ClassificationService, rather than being hardcoded.
    """

    source_type = "audio"

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
        if file.content_type not in ALLOWED_AUDIO_MIME_TYPES:
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
        classification = ClassificationService().classify(
            title=final_title,
            content="",
            original_filename=file.filename,
            mime_type=file.content_type,
        )

        return self._persist(
            organization_id=organization_id,
            created_by=created_by,
            title=final_title,
            content="",
            original_filename=file.filename,
            mime_type=file.content_type,
            file_size=file_size,
            storage_path=storage_path,
            ingestion_status="completed",
            classification=classification,
        )
