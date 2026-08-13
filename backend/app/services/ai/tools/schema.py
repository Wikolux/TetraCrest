"""Pure-Python schema value objects - no external validation library (no
pydantic, no jsonschema). ToolSchema is deliberately minimal: enough
structure for SchemaValidator (validation.py) to check field presence and
primitive types, not a general-purpose schema language.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SchemaField:
    name: str
    type: str
    required: bool = True
    description: str = ""
    default: Any = None


@dataclass(frozen=True)
class ToolSchema:
    fields: tuple[SchemaField, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.fields, tuple):
            object.__setattr__(self, "fields", tuple(self.fields))

    def field_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)

    def required_fields(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields if field.required)

    def get(self, name: str) -> SchemaField | None:
        return next((field for field in self.fields if field.name == name), None)
