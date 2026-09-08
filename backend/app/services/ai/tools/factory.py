from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.ai.tools.registry import ToolRegistry
from app.services.ai.tools.shared.exceptions import ToolNotFoundError
from app.services.tool_implementations.wikipedia_search_tool import WikipediaSearchTool

# P7.15: the platform's first real tool registration - mirrors P7.14's
# own ConversationProviderRegistry.register() precedent exactly.
# ToolFactory is imported by ToolManager, which every specialist that
# uses tools already imports (ResearchAgent's own _default_tool_adapter()
# among them) - so this fires transitively in every real execution path,
# with no separate composition/startup step to remember. The concrete
# tool itself lives outside app/services/ai/ entirely
# (app/services/tool_implementations/) - see its own module docstring
# for why - so this is the one place under app/services/ai/ that is
# allowed to know WikipediaSearchTool exists at all.
ToolRegistry.register(
    "wikipedia_search",
    WikipediaSearchTool,
    name="Wikipedia Search",
    category=ToolCategory.SEARCH,
    capabilities=frozenset({ToolCapability.READ, ToolCapability.NETWORK, ToolCapability.SEARCH}),
    permissions=frozenset({ToolPermission.NETWORK}),
)


class ToolFactory:
    """Resolves a tool_id into a constructed BaseTool via ToolRegistry.
    Nothing else - no lifecycle management, no execution, no policy
    enforcement; those belong to ToolExecutor/ToolManager.

    create() forwards *args/**kwargs to the resolved class's constructor
    rather than one typed config object - tool constructors are
    genuinely tool-specific, the same reasoning as AgentFactory.create().

    WikipediaSearchTool is registered above (P7.15) - the first real
    tool. Every other tool_id remains unregistered until its own concrete
    implementation is added and registered the same way.
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
