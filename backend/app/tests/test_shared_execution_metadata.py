import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.shared.execution_metadata import ExecutionMetadata


def test_defaults():
    metadata = ExecutionMetadata()

    assert metadata.tags == ()
    assert metadata.source is None
    assert metadata.environment is None
    assert dict(metadata.extra) == {}


def test_construction_with_all_fields():
    metadata = ExecutionMetadata(tags=("a", "b"), source="agent", environment="production", extra={"k": "v"})

    assert metadata.tags == ("a", "b")
    assert metadata.source == "agent"
    assert metadata.environment == "production"
    assert metadata.extra["k"] == "v"


def test_tags_is_coerced_to_a_tuple():
    metadata = ExecutionMetadata(tags=["a", "b"])

    assert isinstance(metadata.tags, tuple)
    assert metadata.tags == ("a", "b")


def test_extra_defaults_to_an_empty_read_only_mapping():
    metadata = ExecutionMetadata()

    assert isinstance(metadata.extra, MappingProxyType)


def test_extra_cannot_be_mutated():
    metadata = ExecutionMetadata(extra={"a": 1})

    with pytest.raises(TypeError):
        metadata.extra["a"] = 2


def test_is_frozen():
    metadata = ExecutionMetadata()

    with pytest.raises(dataclasses.FrozenInstanceError):
        metadata.source = "changed"


def test_is_hashable():
    metadata = ExecutionMetadata(tags=("a",), source="agent")

    assert isinstance(hash(metadata), int)


def test_equal_instances_hash_equal():
    first = ExecutionMetadata(tags=("a",), source="agent")
    second = ExecutionMetadata(tags=("a",), source="agent")

    assert first == second
    assert hash(first) == hash(second)
