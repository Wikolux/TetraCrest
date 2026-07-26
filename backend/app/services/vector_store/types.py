from dataclasses import dataclass


@dataclass
class VectorMetadata:
    """Strongly typed metadata attached to a stored vector.

    VectorStore.save_vector still accepts a plain dict (that contract
    isn't changing), so this converts to one via to_dict() at the
    EmbeddingPersistenceService boundary rather than reaching into
    VectorStore/PgVectorStore internals.
    """

    organization_id: int
    resource_type: str
    resource_id: int

    def to_dict(self) -> dict:
        return {
            "organization_id": self.organization_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
        }
