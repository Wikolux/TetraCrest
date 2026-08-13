"""ToolHook - observes a tool invocation's lifecycle without changing it.

Every method is concrete with a no-op default, not abstract - the same
reasoning as RuntimeHook/AgentHook (agents/execution.py has no dedicated
hook ABC, but RuntimeHook's precedent applies directly here too): six hook
points is real, avoidable friction to force-stub if made fully abstract.
Not an ABC - a plain ToolHook() is a valid, fully-functional no-op hook.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.ai.tools.base_tool import BaseTool
    from app.services.ai.tools.context import ToolContext
    from app.services.ai.tools.result import ToolResult


class ToolHook:
    def before_validation(self, context: "ToolContext", tool: "BaseTool") -> None:
        return None

    def after_validation(self, context: "ToolContext", tool: "BaseTool") -> None:
        return None

    def before_execution(self, context: "ToolContext", tool: "BaseTool") -> None:
        return None

    def after_execution(self, context: "ToolContext", result: "ToolResult") -> None:
        return None

    def on_failure(self, context: "ToolContext", error: Exception) -> None:
        return None

    def on_cancel(self, context: "ToolContext") -> None:
        return None
