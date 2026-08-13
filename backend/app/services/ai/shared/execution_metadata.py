"""ExecutionMetadata - a dedicated, structured value object for the
free-form, evolvable data about an execution, kept deliberately separate
from SharedExecutionContext's identity fields (which must never change
once set).

Runtime/Agent-specific contexts use this for their own "-metadata" fields
(runtime_metadata, agent_metadata) instead of a bare mapping, so those
fields carry the same shape (tags/source/environment plus a raw escape
hatch) instead of each layer inventing its own ad-hoc string keys.
SharedExecutionContext itself keeps a plain `metadata` mapping rather than
this richer type - see execution_context.py - to avoid overloading the
one thing every subsystem shares with concerns only some of them need.
"""

from dataclasses import dataclass, field
from types import MappingProxyType

from app.services.ai.shared.execution_types import Metadata


@dataclass(frozen=True)
class ExecutionMetadata:
    tags: tuple[str, ...] = field(default_factory=tuple)
    source: str | None = None
    environment: str | None = None
    extra: Metadata = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.tags, tuple):
            object.__setattr__(self, "tags", tuple(self.tags))
        if not isinstance(self.extra, MappingProxyType):
            object.__setattr__(self, "extra", MappingProxyType(dict(self.extra)))

    def __hash__(self) -> int:
        # extra is a MappingProxyType, which is unhashable - hash on the
        # fields that are, exactly as SharedExecutionContext hashes on
        # execution_id alone rather than its own metadata mapping.
        return hash((self.tags, self.source, self.environment))
