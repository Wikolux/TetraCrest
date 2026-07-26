from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.vector_schema import all_statements
from app.services.vector_store.base_store import VectorStoreError
from database import SessionLocal
from settings import get_settings


class VectorSchemaInitializer:
    """Prepares the PostgreSQL vector-store schema before PgVectorStore runs.

    Provisioning (CREATE EXTENSION/TABLE/INDEX) is infrastructure setup,
    not a data-access concern - PgVectorStore is a pure storage
    implementation that assumes this schema already exists. This mirrors
    how a real migration tool (e.g. Alembic) is run once, out of the
    request path, rather than checked on every query: separating "prepare
    the database" from "use the database" is what let PgVectorStore drop
    its per-call schema check entirely.

    initialize() is idempotent - every statement is IF NOT EXISTS, so
    running it repeatedly (every deploy, every app restart) is safe and
    has no effect after the first successful run.
    """

    def __init__(self, db: Session | None = None):
        self.db = db or SessionLocal()

    def initialize(self, table_name: str | None = None, dimensions: int | None = None) -> None:
        settings = get_settings()
        table_name = table_name or settings.vector_store_table
        dimensions = dimensions or settings.embedding_dimensions

        try:
            for statement in all_statements(table_name, dimensions):
                self.db.execute(text(statement))
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise VectorStoreError(f"Failed to initialize vector store schema: {exc}") from exc
