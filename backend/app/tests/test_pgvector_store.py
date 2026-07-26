import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.services.vector_store.base_store import VectorStoreError
from app.services.vector_store.pgvector_store import PgVectorStore


class _FakeResult:
    def __init__(self, row=None, rowcount=0):
        self._row = row
        self.rowcount = rowcount

    def first(self):
        return self._row


class _FakeSession:
    """Records executed statements instead of talking to a real database.

    Lets PgVectorStore be tested without a running PostgreSQL instance,
    matching how the embedding provider tests mock httpx instead of
    calling a real API.
    """

    def __init__(self, responses=None, raise_on_execute: Exception | None = None):
        self.executed: list[tuple[str, dict]] = []
        self.commits = 0
        self.rollbacks = 0
        self._responses = list(responses or [])
        self._raise_on_execute = raise_on_execute

    def execute(self, statement, params=None):
        if self._raise_on_execute is not None:
            raise self._raise_on_execute
        self.executed.append((str(statement), params or {}))
        if self._responses:
            return self._responses.pop(0)
        return _FakeResult()

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _store(session: _FakeSession) -> PgVectorStore:
    return PgVectorStore(db=session, table_name="embedding_vectors_test", dimensions=3)


def test_save_vector_issues_upsert_and_commits():
    session = _FakeSession()
    store = _store(session)

    store.save_vector("memory:1", [0.1, 0.2, 0.3], metadata={"organization_id": 1})

    insert_calls = [call for call in session.executed if "INSERT INTO" in call[0]]
    assert len(insert_calls) == 1
    _, params = insert_calls[0]
    assert params["vector_id"] == "memory:1"
    assert params["embedding"] == "[0.1,0.2,0.3]"
    assert params["metadata"] == '{"organization_id": 1}'
    assert session.commits >= 1


def test_save_vector_without_metadata_passes_none():
    session = _FakeSession()
    store = _store(session)

    store.save_vector("memory:1", [0.1, 0.2, 0.3])

    _, params = next(call for call in session.executed if "INSERT INTO" in call[0])
    assert params["metadata"] is None


def test_get_vector_returns_parsed_floats_when_row_exists():
    # _schema_ready=True skips the extension/create-table executes, so the
    # single queued response lines up with the SELECT this call issues.
    session = _FakeSession(responses=[_FakeResult(row=("[0.1,0.2,0.3]",))])
    store = _store(session)
    store._schema_ready = True

    result = store.get_vector("memory:1")

    assert result == [0.1, 0.2, 0.3]


def test_get_vector_returns_none_when_row_missing():
    session = _FakeSession(responses=[_FakeResult(row=None)])
    store = _store(session)
    store._schema_ready = True

    assert store.get_vector("missing") is None


def test_delete_vector_returns_true_when_row_deleted():
    session = _FakeSession(responses=[_FakeResult(rowcount=1)])
    store = _store(session)
    store._schema_ready = True

    assert store.delete_vector("memory:1") is True
    assert session.commits >= 1


def test_delete_vector_returns_false_when_nothing_deleted():
    session = _FakeSession(responses=[_FakeResult(rowcount=0)])
    store = _store(session)
    store._schema_ready = True

    assert store.delete_vector("missing") is False


def test_health_check_returns_true_when_query_succeeds():
    session = _FakeSession()
    store = _store(session)

    assert store.health_check() is True


def test_health_check_returns_false_when_query_fails():
    session = _FakeSession(raise_on_execute=SQLAlchemyError("connection refused"))
    store = _store(session)

    assert store.health_check() is False


def test_save_vector_wraps_database_errors(monkeypatch):
    session = _FakeSession()
    store = _store(session)
    store._schema_ready = True  # skip schema setup so the failure targets the insert

    def _raise(*args, **kwargs):
        raise SQLAlchemyError("insert failed")

    monkeypatch.setattr(session, "execute", _raise)

    with pytest.raises(VectorStoreError, match="Failed to save vector"):
        store.save_vector("memory:1", [0.1, 0.2, 0.3])
    assert session.rollbacks >= 1


def test_get_vector_wraps_database_errors(monkeypatch):
    session = _FakeSession()
    store = _store(session)
    store._schema_ready = True

    def _raise(*args, **kwargs):
        raise SQLAlchemyError("select failed")

    monkeypatch.setattr(session, "execute", _raise)

    with pytest.raises(VectorStoreError, match="Failed to fetch vector"):
        store.get_vector("memory:1")


def test_delete_vector_wraps_database_errors(monkeypatch):
    session = _FakeSession()
    store = _store(session)
    store._schema_ready = True

    def _raise(*args, **kwargs):
        raise SQLAlchemyError("delete failed")

    monkeypatch.setattr(session, "execute", _raise)

    with pytest.raises(VectorStoreError, match="Failed to delete vector"):
        store.delete_vector("memory:1")
    assert session.rollbacks >= 1


def test_ensure_schema_wraps_database_errors():
    session = _FakeSession(raise_on_execute=SQLAlchemyError("no permission"))
    store = _store(session)

    with pytest.raises(VectorStoreError, match="Failed to initialize pgvector schema"):
        store.save_vector("memory:1", [0.1, 0.2, 0.3])
