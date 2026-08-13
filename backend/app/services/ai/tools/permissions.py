"""PermissionPolicy - a pure policy value object describing what a tool
invocation is allowed to do. No authorization logic lives here beyond a
single, pure comparison function (missing_permissions) - ToolExecutor
decides what to actually do with the result (deny, emit an event, ...).
"""

from dataclasses import dataclass, field

from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.enums import ToolPermission


@dataclass(frozen=True)
class PermissionPolicy:
    granted_permissions: frozenset[ToolPermission] = field(default_factory=frozenset)
    allow_all: bool = False
    deny_all: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.granted_permissions, frozenset):
            object.__setattr__(self, "granted_permissions", frozenset(self.granted_permissions))


def missing_permissions(tool: BaseTool, policy: PermissionPolicy) -> frozenset[ToolPermission]:
    """Which of `tool`'s required permissions `policy` does not grant.
    Empty means fully permitted. allow_all/deny_all are blanket overrides
    checked before comparing individual permissions."""
    if policy.allow_all:
        return frozenset()
    if policy.deny_all:
        return frozenset(tool.permissions)
    return frozenset(tool.permissions) - policy.granted_permissions
