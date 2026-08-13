import pytest

from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.context import ToolContext
from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.ai.tools.factory import ToolFactory
from app.services.ai.tools.registry import ToolRegistry
from app.services.ai.tools.result import ToolResult
from app.services.ai.tools.schema import ToolSchema
from app.services.ai.tools.shared.exceptions import ToolNotFoundError


class _FakeTool(BaseTool):
    def __init__(self, label="default"):
        self.label = label

    @property
    def tool_id(self) -> str:
        return "fake-tool"

    @property
    def name(self) -> str:
        return "Fake Tool"

    @property
    def description(self) -> str:
        return ""

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CUSTOM_BUSINESS

    @property
    def capabilities(self) -> frozenset[ToolCapability]:
        return frozenset()

    @property
    def permissions(self) -> frozenset[ToolPermission]:
        return frozenset()

    def input_schema(self) -> ToolSchema:
        return ToolSchema()

    def output_schema(self) -> ToolSchema:
        return ToolSchema()

    def validate(self, parameters) -> None:
        return None

    def execute(self, context: ToolContext) -> ToolResult:
        return ToolResult(success=True)

    def health_check(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(ToolRegistry._providers)
    ToolRegistry._providers.clear()
    yield
    ToolRegistry._providers.clear()
    ToolRegistry._providers.update(original)


def test_create_raises_for_an_unknown_tool():
    with pytest.raises(ToolNotFoundError, match="Unknown tool"):
        ToolFactory.create("fake-tool")


def test_create_constructs_the_registered_tool_class():
    ToolRegistry.register("fake-tool", _FakeTool, name="Fake Tool", category=ToolCategory.CUSTOM_BUSINESS)

    tool = ToolFactory.create("fake-tool")

    assert isinstance(tool, _FakeTool)
    assert tool.label == "default"


def test_create_forwards_constructor_arguments():
    ToolRegistry.register("fake-tool", _FakeTool, name="Fake Tool", category=ToolCategory.CUSTOM_BUSINESS)

    tool = ToolFactory.create("fake-tool", label="custom")

    assert tool.label == "custom"


def test_exists_reflects_registry_state():
    assert ToolFactory.exists("fake-tool") is False

    ToolRegistry.register("fake-tool", _FakeTool, name="Fake Tool", category=ToolCategory.CUSTOM_BUSINESS)

    assert ToolFactory.exists("fake-tool") is True


def test_available_lists_every_registered_tool():
    ToolRegistry.register("a", _FakeTool, name="A", category=ToolCategory.SEARCH)
    ToolRegistry.register("b", _FakeTool, name="B", category=ToolCategory.EMAIL)

    assert set(ToolFactory.available()) == {"a", "b"}


def test_the_factory_never_needs_to_change_when_a_new_tool_is_registered():
    class _AnotherTool(_FakeTool):
        pass

    ToolRegistry.register("another", _AnotherTool, name="Another", category=ToolCategory.SEARCH)

    tool = ToolFactory.create("another")

    assert isinstance(tool, _AnotherTool)
