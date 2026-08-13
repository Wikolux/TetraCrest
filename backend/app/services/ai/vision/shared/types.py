"""Reusable vision value objects - generic enough for every future
provider (image/document/extraction/analysis, any vendor) to produce and
for VisionResponse to carry uniformly.
"""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

Metadata = Mapping[str, Any]


@dataclass(frozen=True)
class BoundingBox:
    """A normalized or pixel-space rectangle locating something within an
    image or page - deliberately unit-agnostic (a provider's own metadata
    can record which units apply)."""

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class DetectedObject:
    label: str
    confidence: float = 1.0
    bounding_box: BoundingBox | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class ExtractedText:
    content: str
    confidence: float = 1.0
    bounding_box: BoundingBox | None = None
    language: str | None = None


@dataclass(frozen=True)
class ExtractedTable:
    rows: tuple[tuple[str, ...], ...] = field(default_factory=tuple)
    caption: str | None = None
    bounding_box: BoundingBox | None = None
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.rows, tuple):
            object.__setattr__(self, "rows", tuple(tuple(row) for row in self.rows))


@dataclass(frozen=True)
class VisionCapabilities:
    """The set of capabilities one vision provider declares it supports -
    the same has()-wrapping-a-frozenset shape as
    app.services.ai.agents.capabilities.AgentCapabilities, generalized to
    vision-specific capability enums (ImageCapability/DocumentCapability/
    ExtractionCapability/AnalysisCapability)."""

    declared: frozenset = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not isinstance(self.declared, frozenset):
            object.__setattr__(self, "declared", frozenset(self.declared))

    def has(self, capability: Any) -> bool:
        return capability in self.declared


@dataclass(frozen=True)
class ImageMetadata:
    """Facts about an input image file - not to be confused with
    VisionMetadata (facts about an execution) or ProviderMetadata (facts
    about a provider)."""

    width: int | None = None
    height: int | None = None
    format: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True)
class DocumentMetadata:
    """Facts about an input document file."""

    page_count: int | None = None
    format: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True)
class VisionMetadata:
    """Structured metadata about one vision execution - which capability
    category handled it, how many inputs were processed - distinct from
    ImageMetadata/DocumentMetadata (facts about the input) and from
    app.services.ai.shared.provider_metadata.ProviderMetadata (facts
    about a provider, reused as-is by vision providers rather than
    duplicated here)."""

    capability_category: str | None = None
    input_count: int = 1
    extra: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.extra, MappingProxyType):
            object.__setattr__(self, "extra", MappingProxyType(dict(self.extra)))
