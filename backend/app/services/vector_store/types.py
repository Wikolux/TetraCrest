from dataclasses import dataclass

from app.core.enums import ResourceType


@dataclass
class VectorMetadata:
    """Strongly typed metadata attached to a stored vector.

    VectorStore.save_vector still accepts a plain dict (that contract
    isn't changing), so this converts to one via to_dict() at the
    EmbeddingPersistenceService boundary rather than reaching into
    VectorStore/PgVectorStore internals.

    embedding_model records which model produced the vector (e.g.
    "text-embedding-3-small") - important once more than one model is in
    use, since vectors from different models aren't comparable and a
    future migration/re-index needs to know which rows came from which
    model. Callers don't need to set this: EmbeddingPersistenceService
    stamps it automatically from the configured provider at persistence
    time, overwriting whatever is set here, so it always reflects the
    model that actually generated the vector rather than a caller's
    possibly-stale guess.
    """

    organization_id: int
    resource_type: ResourceType
    resource_id: int
    embedding_model: str | None = None

    def to_dict(self) -> dict:
        return {
            "organization_id": self.organization_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "embedding_model": self.embedding_model,
        }


@dataclass
class SearchResult:
    """One nearest-neighbor match returned by VectorStore.search().

    Generic across resource types on purpose - a future Memory search and
    Conversation search both consume the same shape rather than each
    needing their own result type. `score` is whatever distance/similarity
    measure the concrete VectorStore uses (documented on that store's
    search() implementation); no ranking policy is implied here.
    """

    vector_id: str
    score: float
    metadata: dict | None = None
