from app.models.knowledge_document import KnowledgeDocument
from app.services.ingestion.base_ingestor import BaseIngestor


class YouTubeIngestor(BaseIngestor):
    """Ingests a transcript/metadata from a YouTube video.

    Not yet implemented - transcript retrieval and video metadata extraction
    is a later ingestion-pipeline phase (see .ai/ENTERPRISE_ROADMAP.md,
    Phase 7: YouTube Ingestion). This class exists so the ingestion
    framework has a stable extension point to fill in.
    """

    source_type = "youtube"

    def ingest(
        self,
        video_url: str,
        organization_id: int,
        created_by: int | None = None,
        title: str | None = None,
    ) -> KnowledgeDocument:
        raise NotImplementedError("YouTube ingestion is not yet implemented.")
