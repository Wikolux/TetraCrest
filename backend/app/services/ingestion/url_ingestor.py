import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status

from app.models.knowledge_document import KnowledgeDocument
from app.services.ingestion.base_ingestor import BaseIngestor

REQUEST_TIMEOUT_SECONDS = 10.0

_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TITLE_PAIR_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_TITLE_TAG_RE = re.compile(r"</?title[^>]*>", re.IGNORECASE)


class _ReadableTextExtractor(HTMLParser):
    """Minimal stdlib-only HTML-to-text extractor: collects visible text
    outside of tags.

    Script/style blocks and the <title> are handled separately via regex in
    `URLIngestor._extract` before HTML reaches this parser, rather than
    tracked as parser state here. Python's HTMLParser buffers content inside
    an unclosed element and, at end-of-input, dumps everything from that
    point on as a single literal text chunk instead of continuing to
    tokenize nested tags within it - so a stateful "currently inside a tag
    to skip" tracker would silently swallow the rest of a page whenever a
    <script>/<style>/<title> tag is left unclosed (a realistic malformed-
    HTML case). Stripping/extracting via regex first avoids that failure
    mode entirely.
    """

    def __init__(self):
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data):
        stripped = data.strip()
        if stripped:
            self._chunks.append(stripped)

    def get_text(self) -> str:
        return "\n".join(self._chunks)


class URLIngestor(BaseIngestor):
    """Ingests content fetched from a web URL.

    Downloads the page with a plain HTTP GET and extracts readable text from
    the returned HTML. No AI summarization, embeddings, OCR, YouTube
    handling, JS rendering, or browser automation - those are later phases.
    """

    source_type = "url"

    def ingest(
        self,
        url: str,
        organization_id: int,
        created_by: int | None = None,
        title: str | None = None,
    ) -> KnowledgeDocument:
        self._validate_url(url)
        html = self._download(url)
        extracted_title, extracted_text = self._extract(html)

        return self._persist(
            organization_id=organization_id,
            created_by=created_by,
            title=title or extracted_title or url,
            content=extracted_text,
            source_url=url,
            ingestion_status="completed",
        )

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid URL: {url}",
            )

    def _download(self, url: str) -> str:
        try:
            response = httpx.get(url, timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch URL: {url}",
            ) from exc
        return response.text

    def _extract(self, html: str) -> tuple[str | None, str]:
        title_match = _TITLE_PAIR_RE.search(html)
        title = None
        if title_match:
            collapsed = re.sub(r"\s+", " ", title_match.group(1)).strip()
            title = collapsed or None

        body_html = _SCRIPT_STYLE_RE.sub("", html)
        # Remove only the <title> tag markers (not any text), so a well-formed
        # title's text doesn't confuse the parser and an unclosed <title> in
        # malformed HTML doesn't get treated as never-ending tag content.
        body_html = _TITLE_TAG_RE.sub("", body_html)
        parser = _ReadableTextExtractor()
        parser.feed(body_html)
        parser.close()
        return title, parser.get_text()
