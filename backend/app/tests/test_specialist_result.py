import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.agents.specialists.shared.result import SpecialistResult


def test_defaults():
    result = SpecialistResult(step="retrieve_memory", success=True)

    assert result.output is None
    assert result.error is None


def test_failure_construction():
    result = SpecialistResult(step="invoke_tool", success=False, error="boom")

    assert result.success is False
    assert result.error == "boom"


def test_can_carry_arbitrary_output():
    result = SpecialistResult(step="synthesis", success=True, output={"a": 1})

    assert result.output == {"a": 1}


def test_metadata_defaults_to_empty_read_only_mapping():
    assert isinstance(SpecialistResult(step="s", success=True).metadata, MappingProxyType)


def test_metadata_cannot_be_mutated():
    result = SpecialistResult(step="s", success=True, metadata={"a": 1})

    with pytest.raises(TypeError):
        result.metadata["a"] = 2


def test_is_frozen():
    result = SpecialistResult(step="s", success=True)

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.success = False
