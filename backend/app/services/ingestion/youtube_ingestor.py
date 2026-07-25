import json
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import HTTPException, status
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import CouldNotRetrieveTranscript

from app.models.knowledge_document import KnowledgeDocument
from app.services.classification_service import ClassificationService
from app.services.ingestion.base_ingestor import BaseIngestor

REQUEST_TIMEOUT_SECONDS = 10.0
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
_SHORT_HOST = "youtu.be"


class YouTubeIngestor(BaseIngestor):
    """Ingests a transcript from a YouTube video, plus basic metadata.

    Supports both https://www.youtube.com/watch?v=... and https://youtu.be/...
    URL forms. Retrieves the transcript via the youtube-transcript-api
    library and title/channel via YouTube's public oEmbed endpoint - no
    video download, no audio processing, no browser automation.
    """

    source_type = "youtube"

    def ingest(
        self,
        video_url: str,
        organization_id: int,
        created_by: int | None = None,
        title: str | None = None,
    ) -> KnowledgeDocument:
        video_id = self._extract_video_id(video_url)
        transcript_text = self._fetch_transcript(video_id)
        metadata = self._fetch_metadata(video_url)

        video_title = metadata.get("title")
        channel_name = metadata.get("author_name")

        final_title = title or video_title or video_url
        classification = ClassificationService().classify(title=final_title, content=transcript_text)

        return self._persist(
            organization_id=organization_id,
            created_by=created_by,
            title=final_title,
            content=transcript_text,
            source_url=video_url,
            ingestion_status="completed",
            metadata_json=json.dumps({"video_id": video_id, "channel": channel_name}),
            classification=classification,
        )

    def _extract_video_id(self, video_url: str) -> str:
        parsed = urlparse(video_url)
        host = (parsed.hostname or "").lower()

        video_id = None
        if parsed.scheme in ("http", "https"):
            if host == _SHORT_HOST:
                video_id = parsed.path.lstrip("/").split("/")[0] or None
            elif host in _YOUTUBE_HOSTS and parsed.path == "/watch":
                video_id = parse_qs(parsed.query).get("v", [None])[0]

        if not video_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid YouTube URL: {video_url}",
            )
        return video_id

    def _fetch_transcript(self, video_id: str) -> str:
        try:
            fetched = YouTubeTranscriptApi().fetch(video_id)
        except CouldNotRetrieveTranscript as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No transcript available for video: {video_id}",
            ) from exc
        return " ".join(snippet.text for snippet in fetched).strip()

    def _fetch_metadata(self, video_url: str) -> dict:
        try:
            response = httpx.get(
                "https://www.youtube.com/oembed",
                params={"url": video_url, "format": "json"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            # Metadata is a best-effort enrichment; the transcript is the
            # primary content, so a metadata-fetch failure shouldn't block
            # ingestion. Title/channel simply fall back to their defaults.
            return {}
