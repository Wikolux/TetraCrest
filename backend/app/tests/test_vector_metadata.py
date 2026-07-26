from app.core.enums import ResourceType
from app.services.vector_store.types import SearchResult, VectorMetadata


def test_to_dict_contains_all_fields():
    metadata = VectorMetadata(organization_id=1, resource_type="memory", resource_id=42)

    assert metadata.to_dict() == {
        "organization_id": 1,
        "resource_type": "memory",
        "resource_id": 42,
        "embedding_model": None,
    }


def test_to_dict_accepts_resource_type_enum():
    metadata = VectorMetadata(organization_id=1, resource_type=ResourceType.MEMORY, resource_id=42)

    assert metadata.to_dict() == {
        "organization_id": 1,
        "resource_type": "memory",
        "resource_id": 42,
        "embedding_model": None,
    }
    assert metadata.to_dict()["resource_type"] == ResourceType.MEMORY


def test_embedding_model_defaults_to_none():
    metadata = VectorMetadata(organization_id=1, resource_type="memory", resource_id=42)

    assert metadata.embedding_model is None


def test_to_dict_includes_explicitly_supplied_embedding_model():
    metadata = VectorMetadata(
        organization_id=1, resource_type="memory", resource_id=42, embedding_model="text-embedding-3-small"
    )

    assert metadata.to_dict()["embedding_model"] == "text-embedding-3-small"


# --- SearchResult ------------------------------------------------------


def test_search_result_construction():
    result = SearchResult(vector_id="memory:1", score=0.42, metadata={"organization_id": 1})

    assert result.vector_id == "memory:1"
    assert result.score == 0.42
    assert result.metadata == {"organization_id": 1}


def test_search_result_metadata_defaults_to_none():
    result = SearchResult(vector_id="memory:1", score=0.42)

    assert result.metadata is None
