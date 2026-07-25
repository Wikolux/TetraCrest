from fastapi import UploadFile

from app.models.knowledge_document import KnowledgeDocument
from app.services.ingestion.base_ingestor import BaseIngestor


class VideoIngestor(BaseIngestor):
    """Ingests an uploaded video file, extracting its content (e.g. via
    transcription and/or frame analysis).

    Not yet implemented - video processing is a later ingestion-pipeline
    phase (see .ai/ENTERPRISE_ROADMAP.md). This class exists so the
    ingestion framework has a stable extension point to fill in.
    """

    source_type = "video"

    def ingest(
        self,
        file: UploadFile,
        organization_id: int,
        created_by: int | None = None,
        title: str | None = None,
    ) -> KnowledgeDocument:
        raise NotImplementedError("Video ingestion is not yet implemented.")
