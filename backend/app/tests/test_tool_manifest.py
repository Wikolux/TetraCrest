import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.ai.tools.manifest import ToolManifest
from app.services.ai.tools.schema import ToolSchema


def _manifest(**overrides):
    defaults = dict(
        tool_id="fake-tool",
        name="Fake Tool",
        version="1.0.0",
        description="A fake tool.",
        category=ToolCategory.CUSTOM_BUSINESS,
        capabilities=frozenset({ToolCapability.READ}),
        permissions=frozenset({ToolPermission.FILESYSTEM_READ}),
        input_schema=ToolSchema(),
        output_schema=ToolSchema(),
    )
    defaults.update(overrides)
    return ToolManifest(**defaults)


def test_construction():
    manifest = _manifest()

    assert manifest.tool_id == "fake-tool"
    assert manifest.dependencies == ()
    assert manifest.health_status is None


def test_dependencies_is_coerced_to_a_tuple():
    manifest = _manifest(dependencies=["other-tool"])

    assert manifest.dependencies == ("other-tool",)


def test_capabilities_and_permissions_are_coerced_to_frozensets():
    manifest = _manifest(capabilities=[ToolCapability.READ], permissions=[ToolPermission.NETWORK])

    assert isinstance(manifest.capabilities, frozenset)
    assert isinstance(manifest.permissions, frozenset)


def test_metadata_defaults_to_empty_read_only_mapping():
    assert isinstance(_manifest().metadata, MappingProxyType)


def test_metadata_cannot_be_mutated():
    manifest = _manifest(metadata={"a": 1})

    with pytest.raises(TypeError):
        manifest.metadata["a"] = 2


def test_is_frozen():
    manifest = _manifest()

    with pytest.raises(dataclasses.FrozenInstanceError):
        manifest.version = "2.0.0"
