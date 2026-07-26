from app.services.vector_store.types import VectorMetadata


def test_to_dict_contains_all_fields():
    metadata = VectorMetadata(organization_id=1, resource_type="memory", resource_id=42)

    assert metadata.to_dict() == {
        "organization_id": 1,
        "resource_type": "memory",
        "resource_id": 42,
    }
