import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.db.vector_initializer import VectorSchemaInitializer
from app.services.vector_store.base_store import VectorStoreError
from settings import get_settings


class _FakeSession:
    def __init__(self, raise_on_execute: Exception | None = None):
        self.executed: list[str] = []
        self.commits = 0
        self.rollbacks = 0
        self._raise_on_execute = raise_on_execute

    def execute(self, statement, params=None):
        if self._raise_on_execute is not None:
            raise self._raise_on_execute
        self.executed.append(str(statement))

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_initialize_creates_extension_table_and_indexes():
    session = _FakeSession()
    initializer = VectorSchemaInitializer(db=session)

    initializer.initialize(table_name="embedding_vectors_test", dimensions=3)

    assert any("CREATE EXTENSION" in stmt for stmt in session.executed)
    create_table = next(stmt for stmt in session.executed if "CREATE TABLE" in stmt)
    assert "embedding_vectors_test" in create_table
    assert "organization_id" in create_table
    assert "resource_type" in create_table
    assert "resource_id" in create_table
    assert "vector(3)" in create_table

    index_statements = [stmt for stmt in session.executed if "CREATE INDEX" in stmt]
    assert any("organization_id" in stmt for stmt in index_statements)
    assert any("resource_type" in stmt for stmt in index_statements)
    assert session.commits == 1


def test_initialize_uses_settings_defaults_when_not_given():
    session = _FakeSession()
    initializer = VectorSchemaInitializer(db=session)
    settings = get_settings()

    initializer.initialize()

    create_table = next(stmt for stmt in session.executed if "CREATE TABLE" in stmt)
    assert settings.vector_store_table in create_table


def test_every_statement_is_idempotent_if_not_exists():
    session = _FakeSession()
    initializer = VectorSchemaInitializer(db=session)

    initializer.initialize(table_name="embedding_vectors_test", dimensions=3)

    ddl_statements = [
        stmt
        for stmt in session.executed
        if stmt.startswith("CREATE EXTENSION") or stmt.startswith("CREATE TABLE") or stmt.startswith("CREATE INDEX")
    ]
    assert ddl_statements
    assert all("IF NOT EXISTS" in stmt for stmt in ddl_statements)


def test_initialize_is_safe_to_call_repeatedly():
    session = _FakeSession()
    initializer = VectorSchemaInitializer(db=session)

    initializer.initialize(table_name="embedding_vectors_test", dimensions=3)
    first_run_statement_count = len(session.executed)
    initializer.initialize(table_name="embedding_vectors_test", dimensions=3)

    assert len(session.executed) == first_run_statement_count * 2
    assert session.commits == 2


def test_initialize_wraps_database_errors():
    session = _FakeSession(raise_on_execute=SQLAlchemyError("no permission"))
    initializer = VectorSchemaInitializer(db=session)

    with pytest.raises(VectorStoreError, match="Failed to initialize vector store schema"):
        initializer.initialize(table_name="embedding_vectors_test", dimensions=3)

    assert session.rollbacks == 1
