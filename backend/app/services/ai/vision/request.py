"""VisionRequest - one request into the Vision Framework. Composes
SharedExecutionContext rather than redefining execution identity - the
same pattern RuntimeRequest follows. cancellation_token/parent_shared
reuse app.services.ai.runtime.cancellation.CancellationToken and the
existing SharedExecutionContext.child() mechanism directly, exactly like
RuntimeRequest.parent_shared - never a parallel identity/cancellation
mechanism.

inputs is always a tuple (never a single image/document) so multi-image
reasoning, document batches, and page-by-page processing are supported
from day one without a future breaking change - "Do not assume only one
image" is structural here, not an afterthought.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from app.services.ai.runtime.cancellation import CancellationToken
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.vision.capabilities.enums import VisionCapabilityCategory
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.shared.types import Metadata


class VisionInputKind(StrEnum):
    IMAGE = "image"
    DOCUMENT = "document"


@dataclass(frozen=True)
class VisionInput:
    """One visual input - exactly one of bytes_data/path/url must be
    given; the input can be raw bytes, a filesystem path, or a URL,
    without the framework ever reading any of them itself (no I/O here -
    architecture only)."""

    kind: VisionInputKind
    bytes_data: bytes | None = None
    path: str | None = None
    url: str | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        sources = [source for source in (self.bytes_data, self.path, self.url) if source is not None]
        if len(sources) != 1:
            raise ValueError("VisionInput requires exactly one of bytes_data, path, or url")
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class VisionRequest:
    inputs: tuple[VisionInput, ...]
    capability_category: VisionCapabilityCategory
    shared: SharedExecutionContext = field(default_factory=SharedExecutionContext)
    provider: ProviderName = ProviderName.UNKNOWN
    objective: str = ""
    stream: bool = False
    cancellation_token: "CancellationToken | None" = None
    parent_shared: SharedExecutionContext | None = None
    metadata: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.inputs, tuple):
            object.__setattr__(self, "inputs", tuple(self.inputs))
        if not self.inputs:
            raise ValueError("VisionRequest requires at least one input")
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if not isinstance(self.capability_category, VisionCapabilityCategory):
            # Normalize a plain string ("image") to the real enum member -
            # VisionCapabilityCategory is a StrEnum, so this changes only
            # the field's runtime type, never its equality/hash behavior:
            # dict lookups and comparisons against the literal string keep
            # working exactly as before. An unrecognized value is left as
            # a plain string on purpose - VisionExecutor's existing
            # "Unknown capability_category" check already handles that
            # case, and duplicating that validation here would be a new
            # failure mode, not a routing change.
            try:
                object.__setattr__(self, "capability_category", VisionCapabilityCategory(self.capability_category))
            except ValueError:
                pass
