"""BaseTool - the abstract contract every tool in the AI Operating System
implements.

A tool is a capability, not an agent and not a provider (Capability
Independence / Provider Independence): it executes work and must never
know which model or vendor asked for it - that knowledge belongs entirely
to the Runtime and whichever agent invoked the tool. Every identity/
behavioral member is abstract, with no concrete default - there is no
generically-correct behavior for any of them to fall back to, matching
BaseAgent's own "every future agent must implement these" precedent.

manifest() is the one concrete method: a machine-readable description
(ToolManifest) built entirely from this tool's own abstract members plus
health_check() - every future tool gets automatic discovery/documentation
support for free, without reimplementing anything.
"""

from abc import ABC, abstractmethod

from app.services.ai.tools.context import ToolContext
from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.ai.tools.manifest import ToolManifest
from app.services.ai.tools.result import ToolResult
from app.services.ai.tools.schema import ToolSchema
from app.services.ai.tools.shared.types import Metadata


class BaseTool(ABC):
    @property
    @abstractmethod
    def tool_id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def category(self) -> ToolCategory:
        raise NotImplementedError

    @property
    @abstractmethod
    def capabilities(self) -> frozenset[ToolCapability]:
        raise NotImplementedError

    @property
    @abstractmethod
    def permissions(self) -> frozenset[ToolPermission]:
        raise NotImplementedError

    @property
    def dependencies(self) -> frozenset[str]:
        """Other tool_ids (or external dependency names) this tool needs.
        Concrete default: none - most tools depend on nothing else."""
        return frozenset()

    @abstractmethod
    def input_schema(self) -> ToolSchema:
        raise NotImplementedError

    @abstractmethod
    def output_schema(self) -> ToolSchema:
        raise NotImplementedError

    @abstractmethod
    def validate(self, parameters: Metadata) -> None:
        """Raise if `parameters` is invalid for this tool. Return nothing
        on success. Deterministic - no I/O, no randomness."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, context: ToolContext) -> ToolResult:
        """Do this tool's actual work. Must return a ToolResult - never a
        raw value, never None."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        raise NotImplementedError

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            tool_id=self.tool_id,
            name=self.name,
            version=self.version,
            description=self.description,
            category=self.category,
            capabilities=self.capabilities,
            permissions=self.permissions,
            input_schema=self.input_schema(),
            output_schema=self.output_schema(),
            dependencies=tuple(self.dependencies),
            health_status=self.health_check(),
        )
