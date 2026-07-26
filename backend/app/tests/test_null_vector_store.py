from app.services.vector_store.null_store import NullVectorStore


def test_save_vector_returns_none_without_persisting():
    store = NullVectorStore()

    assert store.save_vector("memory-1", [0.1, 0.2, 0.3]) is None


def test_save_vector_accepts_optional_metadata():
    store = NullVectorStore()

    assert store.save_vector("memory-1", [0.1, 0.2], metadata={"organization_id": 1}) is None


def test_get_vector_always_returns_none():
    store = NullVectorStore()
    store.save_vector("memory-1", [0.1, 0.2, 0.3])

    assert store.get_vector("memory-1") is None


def test_delete_vector_always_returns_true():
    store = NullVectorStore()

    assert store.delete_vector("memory-1") is True
    assert store.delete_vector("never-saved") is True


def test_health_check_always_returns_true():
    store = NullVectorStore()

    assert store.health_check() is True


def test_search_always_returns_no_matches():
    store = NullVectorStore()
    store.save_vector("memory-1", [0.1, 0.2, 0.3], metadata={"organization_id": 1})

    assert store.search([0.1, 0.2, 0.3], organization_id=1) == []


def test_search_accepts_optional_resource_type_and_limit():
    store = NullVectorStore()

    assert store.search([0.1, 0.2], organization_id=1, resource_type="memory", limit=5) == []
