"""Pure-Python validation layer - no external library. Every validator is
a pure function/staticmethod: same inputs always produce the same
ValidationResult, nothing here performs I/O or has side effects.
"""

from dataclasses import dataclass, field

from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.context import ToolContext
from app.services.ai.tools.permissions import PermissionPolicy, missing_permissions
from app.services.ai.tools.policies import ToolExecutionPolicy
from app.services.ai.tools.schema import ToolSchema
from app.services.ai.tools.shared.types import Metadata

_TYPE_CHECKS: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": (list, tuple),
}


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.errors, tuple):
            object.__setattr__(self, "errors", tuple(self.errors))


class SchemaValidator:
    @staticmethod
    def validate(data: Metadata, schema: ToolSchema) -> ValidationResult:
        errors: list[str] = []
        for field_def in schema.fields:
            if field_def.name not in data:
                if field_def.required:
                    errors.append(f"Missing required field: {field_def.name}")
                continue
            expected = _TYPE_CHECKS.get(field_def.type)
            if expected is not None and not isinstance(data[field_def.name], expected):
                errors.append(
                    f"Field '{field_def.name}' expected type {field_def.type}, "
                    f"got {type(data[field_def.name]).__name__}"
                )
        return ValidationResult(valid=not errors, errors=tuple(errors))


class InputValidator:
    @staticmethod
    def validate(tool: BaseTool, parameters: Metadata) -> ValidationResult:
        return SchemaValidator.validate(parameters, tool.input_schema())


class OutputValidator:
    @staticmethod
    def validate(tool: BaseTool, output: Metadata) -> ValidationResult:
        return SchemaValidator.validate(output, tool.output_schema())


class PermissionValidator:
    @staticmethod
    def validate(tool: BaseTool, policy: PermissionPolicy) -> ValidationResult:
        missing = missing_permissions(tool, policy)
        if not missing:
            return ValidationResult(valid=True)
        return ValidationResult(
            valid=False, errors=(f"Missing permissions: {sorted(p.value for p in missing)}",)
        )


class ExecutionPolicyValidator:
    @staticmethod
    def validate(context: ToolContext, policy: ToolExecutionPolicy) -> ValidationResult:
        if context.execution_depth >= policy.maximum_depth:
            return ValidationResult(
                valid=False, errors=(f"Maximum execution depth ({policy.maximum_depth}) exceeded",)
            )
        return ValidationResult(valid=True)
