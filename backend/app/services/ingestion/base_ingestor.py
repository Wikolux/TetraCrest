from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from app.models.knowledge_document import KnowledgeDocument
from app.repositories.knowledge_document_repository import KnowledgeDocumentRepository


class BaseIngestor(ABC):
    """Common contract for every knowledge ingestion source.

    A concrete ingestor is responsible for turning whatever raw input its
    source accepts (an uploaded file, a URL, a YouTube link, ...) into a
    persisted KnowledgeDocument. Every subclass writes through the same
    KnowledgeDocumentRepository via `_persist`, so adding a new source never
    means adding a new persistence path.
    """

    source_type: str = "unknown"

    def __init__(self, db: Session):
        self.db = db
        self.repo = KnowledgeDocumentRepository(db)

    def _persist(self, **fields) -> KnowledgeDocument:
        fields.setdefault("source_type", self.source_type)
        document = KnowledgeDocument(**fields)
        return self.repo.create(document)

    @abstractmethod
    def ingest(self, *args, **kwargs) -> KnowledgeDocument:
        """Ingest from this source and return the persisted KnowledgeDocument."""
        raise NotImplementedError
