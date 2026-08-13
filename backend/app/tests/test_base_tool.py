import pytest

from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.context import ToolContext
from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.ai.tools.manifest import ToolManifest
from app.services.ai.tools.result import ToolResult
from app.services.ai.tools.schema import SchemaField, ToolSchema

_ALL_MEMBERS = (
    "tool_id",
    "name",
    "description",
    "version",
    "category",
    "capabilities",
    "permissions",
    "input_schema",
    "output_schema",
    "validate",
    "execute",
    "health_check",
)


class _FakeTool(BaseTool):
    @property
    def tool_id(self) -> str:
        return "fake-tool"

    @property
    def name(self) -> str:
        return "Fake Tool"

    @property
    def description(self) -> str:
        return "A fake tool for testing."

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CUSTOM_BUSINESS

    @property
    def capabilities(self) -> frozenset[ToolCapability]:
        return frozenset({ToolCapability.READ})

    @property
    def permissions(self) -> frozenset[ToolPermission]:
        return frozenset({ToolPermission.FILESYSTEM_READ})

    def input_schema(self) -> ToolSchema:
        return ToolSchema(fields=(SchemaField(name="query", type="string"),))

    def output_schema(self) -> ToolSchema:
        return ToolSchema(fields=(SchemaField(name="result", type="string"),))

    def validate(self, parameters) -> None:
        if "query" not in parameters:
            raise ValueError("query is required")

    def execute(self, context: ToolContext) -> ToolResult:
        return ToolResult(success=True, output=context.parameters.get("query"))

    def health_check(self) -> bool:
        return True


def test_base_tool_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BaseTool()


@pytest.mark.parametrize(
    "missing_member",
    (m for m in _ALL_MEMBERS if m not in ("dependencies",)),
)
def test_a_subclass_missing_any_required_member_cannot_be_instantiated(missing_member):
    namespace = {}
    for member in _ALL_MEMBERS:
        if member == missing_member:
            continue
        namespace[member] = getattr(_FakeTool, member)

    incomplete = type("IncompleteTool", (BaseTool,), namespace)

    with pytest.raises(TypeError):
        incomplete()


def test_a_complete_subclass_can_be_instantiated():
    assert isinstance(_FakeTool(), BaseTool)


def test_dependencies_defaults_to_an_empty_frozenset():
    assert _FakeTool().dependencies == frozenset()


def test_validate_raises_for_missing_parameters():
    tool = _FakeTool()

    with pytest.raises(ValueError, match="query"):
        tool.validate({})


def test_validate_passes_for_valid_parameters():
    _FakeTool().validate({"query": "hello"})  # must not raise


def test_manifest_composes_every_declared_member():
    tool = _FakeTool()

    manifest = tool.manifest()

    assert isinstance(manifest, ToolManifest)
    assert manifest.tool_id == "fake-tool"
    assert manifest.name == "Fake Tool"
    assert manifest.version == "1.0.0"
    assert manifest.category == ToolCategory.CUSTOM_BUSINESS
    assert manifest.capabilities == frozenset({ToolCapability.READ})
    assert manifest.permissions == frozenset({ToolPermission.FILESYSTEM_READ})
    assert manifest.input_schema == tool.input_schema()
    assert manifest.output_schema == tool.output_schema()
    assert manifest.dependencies == ()
    assert manifest.health_status is True
