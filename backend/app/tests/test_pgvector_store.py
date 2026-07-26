import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.services.vector_store.base_store import VectorStoreError
from app.services.vector_store.pgvector_store import PgVectorStore


class _FakeResult:
    def __init__(self, row=None, rowcount=0, rows=None):
        self._row = row
        self.rowcount = rowcount
        self._rows = rows or []

    def first(self):
        return self._row

    def all(self):
        return self._rows


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


class _FakeMetrics:
    def __init__(self):
        self.successes: list[tuple] = []
        self.failures: list[tuple] = []

    def vector_store_success(self, operation, **context):
        self.successes.append((operation, context))

    def vector_store_failure(self, operation, **context):
        self.failures.append((operation, context))

    # embedding-side methods are unused by PgVectorStore but required by
    # the MetricsRecorder interface if this fake were ever type-checked
    # against it strictly; not needed here since these tests only pass
    # this fake directly to PgVectorStore, which only calls the two above.


def _store(session: _FakeSession, metrics: _FakeMetrics | None = None) -> PgVectorStore:
    return PgVectorStore(db=session, table_name="embedding_vectors_test", dimensions=3, metrics=metrics)


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


# --- schema is no longer PgVectorStore's responsibility (Task 1) ---------


def test_pgvector_store_issues_no_schema_statements():
    """PgVectorStore is a pure storage implementation - schema provisioning
    (CREATE EXTENSION/TABLE/INDEX) is VectorSchemaInitializer's job now,
    not something a save/get/delete/search call triggers implicitly."""
    session = _FakeSession()
    store = _store(session)

    store.save_vector("memory:1", [0.1, 0.2, 0.3])
    store.get_vector("memory:1")
    store.delete_vector("memory:1")
    store.search([0.1, 0.2, 0.3], organization_id=1)

    assert not any("CREATE TABLE" in call[0] for call in session.executed)
    assert not any("CREATE EXTENSION" in call[0] for call in session.executed)
    assert not any("CREATE INDEX" in call[0] for call in session.executed)


# --- tenant-aware storage (Task 1) --------------------------------------


def test_save_vector_extracts_organization_id_resource_type_resource_id_into_columns():
    session = _FakeSession()
    store = _store(session)

    store.save_vector(
        "memory:1",
        [0.1, 0.2, 0.3],
        metadata={"organization_id": 7, "resource_type": "memory", "resource_id": 1},
    )

    _, params = next(call for call in session.executed if "INSERT INTO" in call[0])
    assert params["organization_id"] == 7
    assert params["resource_type"] == "memory"
    assert params["resource_id"] == 1


def test_save_vector_leaves_tenant_columns_none_when_metadata_missing_fields():
    session = _FakeSession()
    store = _store(session)

    store.save_vector("memory:1", [0.1, 0.2, 0.3])

    _, params = next(call for call in session.executed if "INSERT INTO" in call[0])
    assert params["organization_id"] is None
    assert params["resource_type"] is None
    assert params["resource_id"] is None


def test_save_vector_leaves_tenant_columns_none_when_metadata_partial():
    session = _FakeSession()
    store = _store(session)

    store.save_vector("memory:1", [0.1, 0.2, 0.3], metadata={"organization_id": 7})

    _, params = next(call for call in session.executed if "INSERT INTO" in call[0])
    assert params["organization_id"] == 7
    assert params["resource_type"] is None
    assert params["resource_id"] is None


def test_get_vector_returns_parsed_floats_when_row_exists():
    session = _FakeSession(responses=[_FakeResult(row=("[0.1,0.2,0.3]",))])
    store = _store(session)

    result = store.get_vector("memory:1")

    assert result == [0.1, 0.2, 0.3]


def test_get_vector_returns_none_when_row_missing():
    session = _FakeSession(responses=[_FakeResult(row=None)])
    store = _store(session)

    assert store.get_vector("missing") is None


def test_delete_vector_returns_true_when_row_deleted():
    session = _FakeSession(responses=[_FakeResult(rowcount=1)])
    store = _store(session)

    assert store.delete_vector("memory:1") is True
    assert session.commits >= 1


def test_delete_vector_returns_false_when_nothing_deleted():
    session = _FakeSession(responses=[_FakeResult(rowcount=0)])
    store = _store(session)

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

    def _raise(*args, **kwargs):
        raise SQLAlchemyError("insert failed")

    monkeypatch.setattr(session, "execute", _raise)

    with pytest.raises(VectorStoreError, match="Failed to save vector"):
        store.save_vector("memory:1", [0.1, 0.2, 0.3])
    assert session.rollbacks >= 1


def test_get_vector_wraps_database_errors(monkeypatch):
    session = _FakeSession()
    store = _store(session)

    def _raise(*args, **kwargs):
        raise SQLAlchemyError("select failed")

    monkeypatch.setattr(session, "execute", _raise)

    with pytest.raises(VectorStoreError, match="Failed to fetch vector"):
        store.get_vector("memory:1")


def test_delete_vector_wraps_database_errors(monkeypatch):
    session = _FakeSession()
    store = _store(session)

    def _raise(*args, **kwargs):
        raise SQLAlchemyError("delete failed")

    monkeypatch.setattr(session, "execute", _raise)

    with pytest.raises(VectorStoreError, match="Failed to delete vector"):
        store.delete_vector("memory:1")
    assert session.rollbacks >= 1


# --- search (Task 2) -----------------------------------------------------


def test_search_filters_by_organization_id():
    session = _FakeSession(responses=[_FakeResult()])
    store = _store(session)

    store.search([0.1, 0.2, 0.3], organization_id=7)

    select_sql, params = next(call for call in session.executed if "SELECT vector_id" in call[0])
    assert "organization_id = :organization_id" in select_sql
    assert "resource_type = :resource_type" not in select_sql
    assert params["organization_id"] == 7
    assert params["limit"] == 10


def test_search_adds_resource_type_filter_when_given():
    session = _FakeSession(responses=[_FakeResult()])
    store = _store(session)

    store.search([0.1, 0.2, 0.3], organization_id=7, resource_type="memory", limit=5)

    select_sql, params = next(call for call in session.executed if "SELECT vector_id" in call[0])
    assert "resource_type = :resource_type" in select_sql
    assert params["resource_type"] == "memory"
    assert params["limit"] == 5


def test_search_returns_search_results_ordered_by_distance():
    session = _FakeSession(
        responses=[
            _FakeResult(
                rows=[
                    ("memory:1", {"organization_id": 7}, 0.1),
                    ("memory:2", {"organization_id": 7}, 0.9),
                ]
            )
        ]
    )
    store = _store(session)

    results = store.search([0.1, 0.2, 0.3], organization_id=7)

    assert [r.vector_id for r in results] == ["memory:1", "memory:2"]
    assert [r.score for r in results] == [0.1, 0.9]
    assert results[0].metadata == {"organization_id": 7}


def test_search_parses_metadata_returned_as_json_string():
    session = _FakeSession(responses=[_FakeResult(rows=[("memory:1", '{"organization_id": 7}', 0.1)])])
    store = _store(session)

    results = store.search([0.1, 0.2, 0.3], organization_id=7)

    assert results[0].metadata == {"organization_id": 7}


def test_search_wraps_database_errors():
    session = _FakeSession(raise_on_execute=SQLAlchemyError("query failed"))
    store = _store(session)

    with pytest.raises(VectorStoreError, match="Failed to search vectors"):
        store.search([0.1, 0.2, 0.3], organization_id=7)


# --- metrics (Task 2) -----------------------------------------------------


def test_save_vector_records_success_metric():
    session = _FakeSession()
    metrics = _FakeMetrics()
    store = _store(session, metrics=metrics)

    store.save_vector("memory:1", [0.1, 0.2, 0.3])

    assert len(metrics.successes) == 1
    assert metrics.successes[0][0] == "save_vector"
    assert len(metrics.failures) == 0


def test_save_vector_records_failure_metric(monkeypatch):
    session = _FakeSession()
    metrics = _FakeMetrics()
    store = _store(session, metrics=metrics)

    def _raise(*args, **kwargs):
        raise SQLAlchemyError("insert failed")

    monkeypatch.setattr(session, "execute", _raise)

    with pytest.raises(VectorStoreError):
        store.save_vector("memory:1", [0.1, 0.2, 0.3])

    assert len(metrics.failures) == 1
    assert metrics.failures[0][0] == "save_vector"
    assert len(metrics.successes) == 0


def test_get_vector_records_success_and_failure_metrics(monkeypatch):
    session = _FakeSession(responses=[_FakeResult(row=("[0.1,0.2,0.3]",))])
    metrics = _FakeMetrics()
    store = _store(session, metrics=metrics)

    store.get_vector("memory:1")
    assert [op for op, _ in metrics.successes] == ["get_vector"]

    monkeypatch.setattr(session, "execute", lambda *a, **k: (_ for _ in ()).throw(SQLAlchemyError("boom")))
    with pytest.raises(VectorStoreError):
        store.get_vector("memory:1")
    assert [op for op, _ in metrics.failures] == ["get_vector"]


def test_delete_vector_records_success_and_failure_metrics(monkeypatch):
    session = _FakeSession(responses=[_FakeResult(rowcount=1)])
    metrics = _FakeMetrics()
    store = _store(session, metrics=metrics)

    store.delete_vector("memory:1")
    assert [op for op, _ in metrics.successes] == ["delete_vector"]

    monkeypatch.setattr(session, "execute", lambda *a, **k: (_ for _ in ()).throw(SQLAlchemyError("boom")))
    with pytest.raises(VectorStoreError):
        store.delete_vector("memory:1")
    assert [op for op, _ in metrics.failures] == ["delete_vector"]


def test_search_records_success_and_failure_metrics(monkeypatch):
    session = _FakeSession(responses=[_FakeResult(rows=[("memory:1", None, 0.1)])])
    metrics = _FakeMetrics()
    store = _store(session, metrics=metrics)

    store.search([0.1, 0.2, 0.3], organization_id=7)
    assert [op for op, _ in metrics.successes] == ["search"]

    monkeypatch.setattr(session, "execute", lambda *a, **k: (_ for _ in ()).throw(SQLAlchemyError("boom")))
    with pytest.raises(VectorStoreError):
        store.search([0.1, 0.2, 0.3], organization_id=7)
    assert [op for op, _ in metrics.failures] == ["search"]


def test_pgvector_store_defaults_metrics_via_factory():
    from app.metrics.base_recorder import MetricsRecorder
    from app.metrics.safe_recorder import SafeMetricsRecorder

    session = _FakeSession()
    store = PgVectorStore(db=session, table_name="embedding_vectors_test", dimensions=3)

    assert isinstance(store.metrics, MetricsRecorder)
    assert isinstance(store.metrics, SafeMetricsRecorder)


def test_save_vector_succeeds_even_when_metrics_recorder_is_broken():
    """Task 4: observability must never become a production dependency - a
    broken metrics recorder must not stop save_vector from succeeding."""
    from app.metrics.safe_recorder import SafeMetricsRecorder

    class _BrokenRecorder:
        def vector_store_success(self, operation, **context):
            raise RuntimeError("metrics backend unreachable")

        def vector_store_failure(self, operation, **context):
            raise RuntimeError("metrics backend unreachable")

    session = _FakeSession()
    store = _store(session, metrics=SafeMetricsRecorder(_BrokenRecorder()))

    store.save_vector("memory:1", [0.1, 0.2, 0.3])  # must not raise

    assert any("INSERT INTO" in call[0] for call in session.executed)
