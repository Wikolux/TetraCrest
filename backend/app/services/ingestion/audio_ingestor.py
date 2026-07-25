from fastapi import UploadFile

from app.models.knowledge_document import KnowledgeDocument
from app.services.ingestion.base_ingestor import BaseIngestor


class AudioIngestor(BaseIngestor):
    """Ingests an uploaded audio file, extracting its content (e.g. via transcription).

    Not yet implemented - audio transcription is a later ingestion-pipeline
    phase (see .ai/ENTERPRISE_ROADMAP.md, Phase 9: Audio Ingestion). This
    class exists so the ingestion framework has a stable extension point
    to fill in.
    """

    source_type = "audio"

    def ingest(
        self,
        file: UploadFile,
        organization_id: int,
        created_by: int | None = None,
        title: str | None = None,
    ) -> KnowledgeDocument:
        raise NotImplementedError("Audio ingestion is not yet implemented.")
