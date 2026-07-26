import json

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.metrics.base_recorder import MetricsRecorder
from app.metrics.recorder_factory import MetricsRecorderFactory
from app.services.vector_store.base_store import VectorStore, VectorStoreError
from app.services.vector_store.types import SearchResult
from database import SessionLocal
from settings import get_settings


def _serialize_vector(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(value)) for value in vector) + "]"


def _deserialize_vector(raw) -> list[float]:
    if isinstance(raw, list):
        return [float(value) for value in raw]
    return [float(value) for value in raw.strip("[]").split(",") if value]


def _parse_metadata(raw) -> dict | None:
    if raw is None or isinstance(raw, dict):
        return raw
    return json.loads(raw)


def _extract_tenant_fields(metadata: dict | None) -> tuple[int | None, str | None, int | None]:
    if not metadata:
        return None, None, None
    return metadata.get("organization_id"), metadata.get("resource_type"), metadata.get("resource_id")


class PgVectorStore(VectorStore):
    """VectorStore backed by PostgreSQL's pgvector extension.

    A pure storage implementation: it assumes its table (and the pgvector
    extension) already exist, prepared once by VectorSchemaInitializer
    (see app/db/vector_initializer.py) rather than checked on every call.
    Mixing "provision the schema" into a per-request data-access class
    meant every save/get/delete/search paid for a schema check it almost
    never needed, and conflated an infrastructure-provisioning concern
    with a storage concern - separating them is what a real deployment
    needs: schema setup runs once (a migration step, a deploy hook), while
    this class only ever reads/writes rows.

    Persists vectors in a dedicated table (settings.vector_store_table),
    keyed by an opaque vector_id supplied by the caller, rather than adding
    a vector column to Memory or ConversationMessage directly. That keeps
    the vector lifecycle - and any future schema change to it, like an ANN
    index - independent of those domain models and their repositories; any
    number of domain types can reuse this one table by choosing their own
    vector_id (e.g. "memory:42").

    organization_id and resource_type are stored as their own indexed
    columns (extracted from the metadata dict at write time), not just
    inside the metadata JSONB blob - tenant/resource filtering is the
    access pattern every search will use, and filtering through a JSONB
    scan instead of an indexed column would mean every semantic-search
    query degrades to a sequential scan as the table grows. metadata JSONB
    is kept alongside for anything else that doesn't need to be filtered
    on directly (including embedding_model - see VectorMetadata).

    Every operation reports its outcome through MetricsRecorder
    (vector_store_success/vector_store_failure) in addition to raising
    VectorStoreError on failure - metrics are for observability dashboards,
    the exception is for callers that need to react.

    search() uses pgvector's `<->` (Euclidean distance) operator to find
    the nearest stored vectors, filtered first by the indexed
    organization_id (and optionally resource_type) columns. This is a
    storage-level nearest-neighbor lookup only - no ranking policy,
    thresholding, or multi-strategy retrieval; that belongs to a future
    semantic-search service.
    """

    def __init__(
        self,
        db: Session | None = None,
        table_name: str | None = None,
        dimensions: int | None = None,
        metrics: MetricsRecorder | None = None,
    ):
        settings = get_settings()
        self.db = db or SessionLocal()
        self.table_name = table_name or settings.vector_store_table
        self.dimensions = dimensions or settings.embedding_dimensions
        self.metrics = metrics or MetricsRecorderFactory.create()

    def save_vector(self, vector_id: str, vector: list[float], metadata: dict | None = None) -> None:
        organization_id, resource_type, resource_id = _extract_tenant_fields(metadata)
        try:
            self.db.execute(
                text(
                    f"INSERT INTO {self.table_name} "
                    "(vector_id, organization_id, resource_type, resource_id, embedding, metadata) "
                    "VALUES (:vector_id, :organization_id, :resource_type, :resource_id, "
                    "CAST(:embedding AS vector), CAST(:metadata AS jsonb)) "
                    "ON CONFLICT (vector_id) DO UPDATE SET "
                    "organization_id = EXCLUDED.organization_id, "
                    "resource_type = EXCLUDED.resource_type, "
                    "resource_id = EXCLUDED.resource_id, "
                    "embedding = EXCLUDED.embedding, "
                    "metadata = EXCLUDED.metadata"
                ),
                {
                    "vector_id": vector_id,
                    "organization_id": organization_id,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "embedding": _serialize_vector(vector),
                    "metadata": json.dumps(metadata) if metadata is not None else None,
                },
            )
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            self.metrics.vector_store_failure(operation="save_vector", vector_id=vector_id)
            raise VectorStoreError(f"Failed to save vector '{vector_id}': {exc}") from exc
        self.metrics.vector_store_success(operation="save_vector", vector_id=vector_id)

    def get_vector(self, vector_id: str) -> list[float] | None:
        try:
            row = self.db.execute(
                text(f"SELECT embedding FROM {self.table_name} WHERE vector_id = :vector_id"),
                {"vector_id": vector_id},
            ).first()
        except SQLAlchemyError as exc:
            self.metrics.vector_store_failure(operation="get_vector", vector_id=vector_id)
            raise VectorStoreError(f"Failed to fetch vector '{vector_id}': {exc}") from exc

        self.metrics.vector_store_success(operation="get_vector", vector_id=vector_id)
        if row is None:
            return None
        return _deserialize_vector(row[0])

    def delete_vector(self, vector_id: str) -> bool:
        try:
            result = self.db.execute(
                text(f"DELETE FROM {self.table_name} WHERE vector_id = :vector_id"),
                {"vector_id": vector_id},
            )
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            self.metrics.vector_store_failure(operation="delete_vector", vector_id=vector_id)
            raise VectorStoreError(f"Failed to delete vector '{vector_id}': {exc}") from exc
        self.metrics.vector_store_success(operation="delete_vector", vector_id=vector_id)
        return result.rowcount > 0

    def health_check(self) -> bool:
        try:
            self.db.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False

    def search(
        self,
        query_vector: list[float],
        organization_id: int,
        resource_type: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Nearest-neighbor lookup by Euclidean distance (pgvector `<->`).

        score is the raw distance - lower means more similar. Always
        scoped to organization_id (indexed column), optionally further
        narrowed to resource_type (also indexed).
        """
        conditions = ["organization_id = :organization_id"]
        params: dict = {
            "organization_id": organization_id,
            "query_vector": _serialize_vector(query_vector),
            "limit": limit,
        }
        if resource_type is not None:
            conditions.append("resource_type = :resource_type")
            params["resource_type"] = resource_type
        where_clause = " AND ".join(conditions)

        try:
            rows = self.db.execute(
                text(
                    "SELECT vector_id, metadata, embedding <-> CAST(:query_vector AS vector) AS distance "
                    f"FROM {self.table_name} WHERE {where_clause} "
                    "ORDER BY distance ASC LIMIT :limit"
                ),
                params,
            ).all()
        except SQLAlchemyError as exc:
            self.metrics.vector_store_failure(operation="search", organization_id=organization_id)
            raise VectorStoreError(f"Failed to search vectors: {exc}") from exc

        self.metrics.vector_store_success(
            operation="search", organization_id=organization_id, result_count=len(rows)
        )
        return [
            SearchResult(vector_id=row[0], score=float(row[2]), metadata=_parse_metadata(row[1]))
            for row in rows
        ]
