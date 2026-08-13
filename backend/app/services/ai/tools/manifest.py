"""ToolManifest - a machine-readable description of one tool: identity,
version, capabilities, schemas, permissions, dependencies, health status,
and metadata, in one immutable value object.

This is the foundation for automatic tool discovery, self-documenting
APIs, visual workflow builders, tool marketplaces, business-specific OS
generation, automatic compatibility checks, future MCP interoperability,
and autonomous agent planning ("which tool can solve this task") -
building it into the framework now (BaseTool.manifest(), a concrete
method every tool gets for free) is far cheaper than retrofitting it onto
hundreds of tools later.

Pure data - no BaseTool import here. BaseTool.manifest() constructs one
from its own abstract members; this module has no dependency on BaseTool
itself, so there is no import cycle between the two.
"""

from dataclasses import dataclass, field
from types import MappingProxyType

from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.ai.tools.schema import ToolSchema
from app.services.ai.tools.shared.types import Metadata


@dataclass(frozen=True)
class ToolManifest:
    tool_id: str
    name: str
    version: str
    description: str
    category: ToolCategory
    capabilities: frozenset[ToolCapability]
    permissions: frozenset[ToolPermission]
    input_schema: ToolSchema
    output_schema: ToolSchema
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    health_status: bool | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.dependencies, tuple):
            object.__setattr__(self, "dependencies", tuple(self.dependencies))
        if not isinstance(self.capabilities, frozenset):
            object.__setattr__(self, "capabilities", frozenset(self.capabilities))
        if not isinstance(self.permissions, frozenset):
            object.__setattr__(self, "permissions", frozenset(self.permissions))
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
