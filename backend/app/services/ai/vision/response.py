"""VisionResponse - the Vision Framework's public, single result for one
VisionRequest. Composes ExecutionMetrics (app.services.ai.kernel.metrics)
rather than a new metrics type - the same shape RuntimeResponse/
ToolResult/SpecialistResponse already use.

execution_id/parent_execution_id/correlation_id/causation_id are copied
directly from whatever SharedExecutionContext produced this response,
the same identity-propagation pattern every execution artifact in this
platform follows.
"""

import uuid
from dataclasses import dataclass, field
from types import MappingProxyType

from app.services.ai.kernel.metrics import ExecutionMetrics
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.shared.types import (
    DetectedObject,
    ExtractedTable,
    ExtractedText,
    Metadata,
    VisionMetadata,
)


@dataclass(frozen=True)
class VisionResponse:
    success: bool
    extracted_text: tuple[ExtractedText, ...] = field(default_factory=tuple)
    tables: tuple[ExtractedTable, ...] = field(default_factory=tuple)
    objects: tuple[DetectedObject, ...] = field(default_factory=tuple)
    structured_output: Metadata | None = None
    confidence: float = 0.0
    provider: ProviderName | None = None
    model: str | None = None
    duration_ms: float = 0.0
    metrics: ExecutionMetrics | None = None
    error: str | None = None
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_execution_id: str | None = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: str | None = None
    vision_metadata: VisionMetadata | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        for tuple_field in ("extracted_text", "tables", "objects"):
            value = getattr(self, tuple_field)
            if not isinstance(value, tuple):
                object.__setattr__(self, tuple_field, tuple(value))
        if self.structured_output is not None and not isinstance(self.structured_output, MappingProxyType):
            object.__setattr__(self, "structured_output", MappingProxyType(dict(self.structured_output)))
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
