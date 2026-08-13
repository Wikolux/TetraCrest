from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.enums import ResourceType
from app.repositories.conversation_message_repository import ConversationMessageRepository
from app.repositories.memory_repository import MemoryRepository
from app.services.embedding_service import EmbeddingService
from app.services.vector_store.base_store import VectorStore
from app.services.vector_store.store_factory import VectorStoreFactory
from app.services.vector_store.types import SearchResult
from database import SessionLocal


@dataclass
class SemanticSearchResult:
    """One hydrated semantic-search hit.

    The only shape SemanticSearchService ever returns - callers never see
    a raw VectorStore.SearchResult (its vector_id, or any detail of how/
    where the vector is stored).

    similarity_score is passed through unchanged from VectorStore.search():
    for the current PgVectorStore backend that's a Euclidean distance
    (lower means more similar), not a normalized 0-1 similarity. Results
    are always already ordered best-first by the store; this service does
    not recompute, invert, or re-rank that ordering.

    created_at is exposed (read from the underlying Memory/
    ConversationMessage row) purely as data - this service does not use it
    for anything itself. It's here so a future ranking step has the
    recency signal it needs without SemanticSearchService taking on any
    ranking responsibility of its own.
    """

    resource_type: str
    resource_id: int
    content: str
    similarity_score: float
    created_at: datetime
    metadata: dict | None = None


class SemanticSearchService:
    """Retrieves the memories/conversation messages most relevant to a
    natural-language query.

    Composes EmbeddingService (query text -> vector) with VectorStore.search
    (vector -> nearest stored vectors) and the domain repositories (a match
    -> the actual row) - the same generate-then-act composition
    EmbeddingPersistenceService already does for writes, mirrored here for
    reads. Deliberately does not use EmbeddingPersistenceService: that
    service couples generation with persistence, and a search neither
    generates a vector to store nor needs that coupling - it only needs
    EmbeddingService's generation half.

    Ranking is exactly whatever VectorStore.search() already computed -
    this service never re-ranks, applies a relevance threshold, or blends
    in any other signal; it only resolves each match to its underlying
    row and skips matches it can't verify (deleted resource, or an id that
    doesn't belong to the requesting organization).

    Errors from the embedding provider or vector store propagate
    unchanged - a failed search must be visibly a failure, not a silently
    empty result set. This is the opposite of the write path
    (AIMemoryService/ConversationMessageService), where embedding failures
    are swallowed because there's a successful save to protect; a read has
    no side effect to protect, so hiding the error would only mislead a
    caller into thinking nothing matched.
    """

    def __init__(
        self,
        db: Session | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
        memory_repository: MemoryRepository | None = None,
        conversation_message_repository: ConversationMessageRepository | None = None,
    ):
        self.db = db or SessionLocal()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStoreFactory.create()
        self.memory_repository = memory_repository or MemoryRepository(self.db)
        self.conversation_message_repository = (
            conversation_message_repository or ConversationMessageRepository(self.db)
        )

    def search_memories(
        self, query: str, organization_id: int, limit: int = 10
    ) -> list[SemanticSearchResult]:
        return self._search(query, organization_id, ResourceType.MEMORY, limit)

    def search_conversation_messages(
        self, query: str, organization_id: int, limit: int = 10
    ) -> list[SemanticSearchResult]:
        return self._search(query, organization_id, ResourceType.CONVERSATION_MESSAGE, limit)

    def search_all(
        self, query: str, organization_id: int, limit: int = 10
    ) -> list[SemanticSearchResult]:
        return self._search(query, organization_id, resource_type=None, limit=limit)

    def _search(
        self, query: str, organization_id: int, resource_type: str | None, limit: int
    ) -> list[SemanticSearchResult]:
        query_vector = self.embedding_service.generate_embedding(query)
        matches = self.vector_store.search(
            query_vector, organization_id=organization_id, resource_type=resource_type, limit=limit
        )
        return self._hydrate(matches, organization_id)

    def _hydrate(self, matches: list[SearchResult], organization_id: int) -> list[SemanticSearchResult]:
        memory_ids = [
            match.metadata["resource_id"]
            for match in matches
            if match.metadata and match.metadata.get("resource_type") == ResourceType.MEMORY
        ]
        message_ids = [
            match.metadata["resource_id"]
            for match in matches
            if match.metadata and match.metadata.get("resource_type") == ResourceType.CONVERSATION_MESSAGE
        ]

        memories_by_id = (
            {
                memory.id: memory
                for memory in self.memory_repository.get_many_for_organization(memory_ids, organization_id)
            }
            if memory_ids
            else {}
        )
        messages_by_id = (
            {
                message.id: message
                for message in self.conversation_message_repository.get_many_for_organization(
                    message_ids, organization_id
                )
            }
            if message_ids
            else {}
        )

        results = []
        for match in matches:
            metadata = match.metadata or {}
            resource_type = metadata.get("resource_type")
            resource_id = metadata.get("resource_id")

            if resource_type == ResourceType.MEMORY:
                resource = memories_by_id.get(resource_id)
            elif resource_type == ResourceType.CONVERSATION_MESSAGE:
                resource = messages_by_id.get(resource_id)
            else:
                resource = None

            if resource is None:
                # Stale vector row (resource since deleted) or an id that
                # doesn't belong to this organization - skip rather than
                # error, since search must never surface a resource it
                # can't verify belongs to the requesting tenant.
                continue

            results.append(
                SemanticSearchResult(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    content=resource.content,
                    similarity_score=match.score,
                    created_at=resource.created_at,
                    metadata=metadata,
                )
            )
        return results
