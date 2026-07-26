import json

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.vector_store.base_store import VectorStore, VectorStoreError
from database import SessionLocal
from settings import get_settings


def _serialize_vector(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(value)) for value in vector) + "]"


def _deserialize_vector(raw) -> list[float]:
    if isinstance(raw, list):
        return [float(value) for value in raw]
    return [float(value) for value in raw.strip("[]").split(",") if value]


class PgVectorStore(VectorStore):
    """VectorStore backed by PostgreSQL's pgvector extension.

    Persists vectors in a dedicated table (settings.vector_store_table),
    keyed by an opaque vector_id supplied by the caller, rather than adding
    a vector column to Memory or ConversationMessage directly. That keeps
    the vector lifecycle - and any future schema change to it, like an ANN
    index - independent of those domain models and their repositories; any
    number of domain types can reuse this one table by choosing their own
    vector_id (e.g. "memory:42").

    Schema is managed here via raw SQL rather than a shared SQLAlchemy ORM
    model, because pgvector's `vector` column type has no SQLite
    equivalent - every existing test builds its schema against an
    in-memory SQLite database via `Base.metadata.create_all`, and
    registering a pgvector-typed model on that shared Base would break
    every one of those tests. This store is unit-tested against a mocked
    Session instead of the shared SQLite fixtures.

    No similarity search happens here - only save/get/delete by vector_id
    and a health check. Storing embeddings as a genuine `vector` column
    (rather than plain text/array) now means a future milestone can add
    ANN search without a column-type migration.
    """

    def __init__(
        self,
        db: Session | None = None,
        table_name: str | None = None,
        dimensions: int | None = None,
    ):
        settings = get_settings()
        self.db = db or SessionLocal()
        self.table_name = table_name or settings.vector_store_table
        self.dimensions = dimensions or settings.embedding_dimensions
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        try:
            self.db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            self.db.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS {self.table_name} ("
                    "vector_id VARCHAR(255) PRIMARY KEY, "
                    f"embedding vector({self.dimensions}) NOT NULL, "
                    "metadata JSONB, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT now())"
                )
            )
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise VectorStoreError(f"Failed to initialize pgvector schema: {exc}") from exc
        self._schema_ready = True

    def save_vector(self, vector_id: str, vector: list[float], metadata: dict | None = None) -> None:
        self._ensure_schema()
        try:
            self.db.execute(
                text(
                    f"INSERT INTO {self.table_name} (vector_id, embedding, metadata) "
                    "VALUES (:vector_id, CAST(:embedding AS vector), CAST(:metadata AS jsonb)) "
                    "ON CONFLICT (vector_id) DO UPDATE SET "
                    "embedding = EXCLUDED.embedding, metadata = EXCLUDED.metadata"
                ),
                {
                    "vector_id": vector_id,
                    "embedding": _serialize_vector(vector),
                    "metadata": json.dumps(metadata) if metadata is not None else None,
                },
            )
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise VectorStoreError(f"Failed to save vector '{vector_id}': {exc}") from exc

    def get_vector(self, vector_id: str) -> list[float] | None:
        self._ensure_schema()
        try:
            row = self.db.execute(
                text(f"SELECT embedding FROM {self.table_name} WHERE vector_id = :vector_id"),
                {"vector_id": vector_id},
            ).first()
        except SQLAlchemyError as exc:
            raise VectorStoreError(f"Failed to fetch vector '{vector_id}': {exc}") from exc

        if row is None:
            return None
        return _deserialize_vector(row[0])

    def delete_vector(self, vector_id: str) -> bool:
        self._ensure_schema()
        try:
            result = self.db.execute(
                text(f"DELETE FROM {self.table_name} WHERE vector_id = :vector_id"),
                {"vector_id": vector_id},
            )
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise VectorStoreError(f"Failed to delete vector '{vector_id}': {exc}") from exc
        return result.rowcount > 0

    def health_check(self) -> bool:
        try:
            self.db.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False
