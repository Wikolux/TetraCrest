"""ToolAdapter - a thin wrapper over the existing ToolManager. Never
executes a tool directly (never touches ToolRegistry/ToolFactory/
ToolExecutor itself) - every call passes straight through to the one
existing entry point every agent uses.
"""

from app.services.ai.tools.manager import ToolManager
from app.services.ai.tools.result import ToolResult
from app.services.ai.tools.shared.types import Metadata


class ToolAdapter:
    def __init__(self, manager: ToolManager | None = None) -> None:
        self.manager = manager or ToolManager()

    def invoke(self, tool_id: str, parameters: Metadata | None = None, **kwargs) -> ToolResult:
        return self.manager.invoke(tool_id, parameters, **kwargs)
