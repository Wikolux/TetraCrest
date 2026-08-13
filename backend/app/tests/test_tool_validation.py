from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.context import ToolContext
from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.ai.tools.permissions import PermissionPolicy
from app.services.ai.tools.policies import ToolExecutionPolicy
from app.services.ai.tools.result import ToolResult
from app.services.ai.tools.schema import SchemaField, ToolSchema
from app.services.ai.tools.validation import (
    ExecutionPolicyValidator,
    InputValidator,
    OutputValidator,
    PermissionValidator,
    SchemaValidator,
    ValidationResult,
)


class _FakeTool(BaseTool):
    def __init__(self, permissions=()):
        self._permissions = frozenset(permissions)

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
        return self._permissions

    def input_schema(self) -> ToolSchema:
        return ToolSchema(fields=(SchemaField(name="query", type="string"),))

    def output_schema(self) -> ToolSchema:
        return ToolSchema(fields=(SchemaField(name="result", type="string"),))

    def validate(self, parameters) -> None:
        return None

    def execute(self, context: ToolContext) -> ToolResult:
        return ToolResult(success=True)

    def health_check(self) -> bool:
        return True


# --- ValidationResult ---------------------------------------------------------------


def test_validation_result_errors_is_coerced_to_a_tuple():
    result = ValidationResult(valid=False, errors=["a", "b"])

    assert result.errors == ("a", "b")


# --- SchemaValidator --------------------------------------------------------------------


def test_schema_validator_passes_when_every_required_field_is_present_and_typed():
    schema = ToolSchema(fields=(SchemaField(name="query", type="string"),))

    result = SchemaValidator.validate({"query": "hi"}, schema)

    assert result.valid is True
    assert result.errors == ()


def test_schema_validator_reports_a_missing_required_field():
    schema = ToolSchema(fields=(SchemaField(name="query", type="string"),))

    result = SchemaValidator.validate({}, schema)

    assert result.valid is False
    assert "query" in result.errors[0]


def test_schema_validator_allows_a_missing_optional_field():
    schema = ToolSchema(fields=(SchemaField(name="query", type="string", required=False),))

    result = SchemaValidator.validate({}, schema)

    assert result.valid is True


def test_schema_validator_reports_a_type_mismatch():
    schema = ToolSchema(fields=(SchemaField(name="count", type="integer"),))

    result = SchemaValidator.validate({"count": "not a number"}, schema)

    assert result.valid is False
    assert "count" in result.errors[0]


def test_schema_validator_accepts_extra_fields_not_in_the_schema():
    schema = ToolSchema(fields=(SchemaField(name="query", type="string"),))

    result = SchemaValidator.validate({"query": "hi", "extra": 123}, schema)

    assert result.valid is True


def test_schema_validator_number_type_accepts_int_and_float():
    schema = ToolSchema(fields=(SchemaField(name="amount", type="number"),))

    assert SchemaValidator.validate({"amount": 5}, schema).valid is True
    assert SchemaValidator.validate({"amount": 5.5}, schema).valid is True


def test_schema_validator_empty_schema_always_passes():
    assert SchemaValidator.validate({"anything": "goes"}, ToolSchema()).valid is True


# --- InputValidator / OutputValidator -----------------------------------------------------


def test_input_validator_uses_the_tools_input_schema():
    tool = _FakeTool()

    assert InputValidator.validate(tool, {}).valid is False
    assert InputValidator.validate(tool, {"query": "hi"}).valid is True


def test_output_validator_uses_the_tools_output_schema():
    tool = _FakeTool()

    assert OutputValidator.validate(tool, {}).valid is False
    assert OutputValidator.validate(tool, {"result": "hi"}).valid is True


# --- PermissionValidator ---------------------------------------------------------------


def test_permission_validator_passes_when_nothing_is_required():
    assert PermissionValidator.validate(_FakeTool(), PermissionPolicy()).valid is True


def test_permission_validator_fails_when_a_required_permission_is_missing():
    tool = _FakeTool(permissions=(ToolPermission.NETWORK,))

    result = PermissionValidator.validate(tool, PermissionPolicy())

    assert result.valid is False
    assert "network" in result.errors[0]


# --- ExecutionPolicyValidator -----------------------------------------------------------


def test_execution_policy_validator_passes_below_maximum_depth():
    context = ToolContext("fake-tool", execution_depth=1)

    assert ExecutionPolicyValidator.validate(context, ToolExecutionPolicy(maximum_depth=5)).valid is True


def test_execution_policy_validator_fails_at_maximum_depth():
    context = ToolContext("fake-tool", execution_depth=5)

    result = ExecutionPolicyValidator.validate(context, ToolExecutionPolicy(maximum_depth=5))

    assert result.valid is False
    assert "depth" in result.errors[0].lower()
