from fastapi import UploadFile

from app.models.knowledge_document import KnowledgeDocument
from app.services.ingestion.base_ingestor import BaseIngestor


class ImageIngestor(BaseIngestor):
    """Ingests an uploaded image, extracting its content (e.g. via OCR).

    Not yet implemented - OCR/text extraction from images is a later
    ingestion-pipeline phase (see .ai/ENTERPRISE_ROADMAP.md, Phase 8: Image
    Ingestion). This class exists so the ingestion framework has a stable
    extension point to fill in.
    """

    source_type = "image"

    def ingest(
        self,
        file: UploadFile,
        organization_id: int,
        created_by: int | None = None,
        title: str | None = None,
    ) -> KnowledgeDocument:
        raise NotImplementedError("Image ingestion is not yet implemented.")
