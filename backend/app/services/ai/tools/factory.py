from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.registry import ToolRegistry
from app.services.ai.tools.shared.exceptions import ToolNotFoundError


class ToolFactory:
    """Resolves a tool_id into a constructed BaseTool via ToolRegistry.
    Nothing else - no lifecycle management, no execution, no policy
    enforcement; those belong to ToolExecutor/ToolManager.

    create() forwards *args/**kwargs to the resolved class's constructor
    rather than one typed config object - tool constructors are
    genuinely tool-specific, the same reasoning as AgentFactory.create().
    """

    @staticmethod
    def create(tool_id: str, *args, **kwargs) -> BaseTool:
        tool_class = ToolRegistry.get(tool_id)
        if tool_class is None:
            raise ToolNotFoundError(f"Unknown tool: {tool_id}")
        return tool_class(*args, **kwargs)

    @staticmethod
    def exists(tool_id: str) -> bool:
        return ToolRegistry.exists(tool_id)

    @staticmethod
    def available() -> tuple[str, ...]:
        return ToolRegistry.available()
