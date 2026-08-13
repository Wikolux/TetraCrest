"""ToolDiscovery - finds registered tool_ids by category, capability,
permission, name, or tool_id directly.

Simple indexed architecture, not a search engine: every lookup is a
linear scan (or direct dict access) over ToolRegistry.all_registrations(),
which is registration-time metadata - no tool is ever instantiated to
answer a discovery query.
"""

from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.ai.tools.registry import ToolRegistry


class ToolDiscovery:
    def __init__(self, registry: type[ToolRegistry] = ToolRegistry) -> None:
        self.registry = registry

    def by_category(self, category: ToolCategory) -> tuple[str, ...]:
        return tuple(
            tool_id
            for tool_id, registration in self.registry.all_registrations().items()
            if registration.category == category
        )

    def by_capability(self, capability: ToolCapability) -> tuple[str, ...]:
        return tuple(
            tool_id
            for tool_id, registration in self.registry.all_registrations().items()
            if capability in registration.capabilities
        )

    def by_permission(self, permission: ToolPermission) -> tuple[str, ...]:
        return tuple(
            tool_id
            for tool_id, registration in self.registry.all_registrations().items()
            if permission in registration.permissions
        )

    def by_name(self, name: str) -> tuple[str, ...]:
        return tuple(
            tool_id
            for tool_id, registration in self.registry.all_registrations().items()
            if registration.name == name
        )

    def by_tool_id(self, tool_id: str) -> str | None:
        return tool_id if self.registry.exists(tool_id) else None
