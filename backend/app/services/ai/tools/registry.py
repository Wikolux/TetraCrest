"""ToolRegistry - maps a tool_id to a registered tool class plus the
declared metadata (name/category/capabilities/permissions) needed for
discovery, all supplied at registration time.

Declaring category/capabilities/permissions as part of register() rather
than deriving them by instantiating the tool class is a deliberate
design choice: category/capabilities/permissions are abstract *instance*
properties on BaseTool (each concrete tool decides its own values), so a
registry holding only *classes* cannot answer "what category is this"
without constructing one - and tool constructors aren't standardized on
one shape (mirrors why AgentFactory.create() takes *args/**kwargs, not one
config type). Requiring the caller to state this once at registration -
exactly when a tool already knows its own identity - means
categories()/capabilities() work directly off the registry, with no
instantiation needed anywhere in discovery.

Built on GenericProviderRegistry (app.services.ai.shared.provider_registry),
the same base ConversationProviderRegistry/AgentRegistry/SpecialistRegistry
use: class-level shared state, guarded by a re-entrant lock, duplicate
registration rejected unless overwrite=True. Tools self-register; nothing
here or in ToolFactory needs modification when a new tool is added
(Open/Closed). register()/get() are overridden because a plain
GenericProviderRegistry stores TValue directly under TKey, whereas
ToolRegistry needs to store a whole ToolRegistration (the tool class plus
its declared metadata) and hand back just the tool_class from get() -
get_registration() reaches the full record when the metadata is needed too.
"""

from dataclasses import dataclass, field

from app.services.ai.shared.provider_registry import GenericProviderRegistry
from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.ai.tools.shared.exceptions import ToolError


@dataclass(frozen=True)
class ToolRegistration:
    tool_class: type[BaseTool]
    name: str
    category: ToolCategory
    capabilities: frozenset[ToolCapability] = field(default_factory=frozenset)
    permissions: frozenset[ToolPermission] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not isinstance(self.capabilities, frozenset):
            object.__setattr__(self, "capabilities", frozenset(self.capabilities))
        if not isinstance(self.permissions, frozenset):
            object.__setattr__(self, "permissions", frozenset(self.permissions))


class ToolRegistry(GenericProviderRegistry[str, ToolRegistration]):
    _registration_error = ToolError

    @classmethod
    def register(
        cls,
        tool_id: str,
        tool_class: type[BaseTool],
        *,
        name: str,
        category: ToolCategory,
        capabilities: frozenset[ToolCapability] = frozenset(),
        permissions: frozenset[ToolPermission] = frozenset(),
        overwrite: bool = False,
    ) -> None:
        registration = ToolRegistration(
            tool_class=tool_class,
            name=name,
            category=category,
            capabilities=frozenset(capabilities),
            permissions=frozenset(permissions),
        )
        super().register(tool_id, registration, overwrite=overwrite)

    @classmethod
    def exists(cls, tool_id: str) -> bool:
        return cls.is_registered(tool_id)

    @classmethod
    def get(cls, tool_id: str) -> type[BaseTool] | None:
        registration = super().get(tool_id)
        return registration.tool_class if registration else None

    @classmethod
    def get_registration(cls, tool_id: str) -> ToolRegistration | None:
        return super().get(tool_id)

    @classmethod
    def available(cls) -> tuple[str, ...]:
        return tuple(cls.all_registered().keys())

    @classmethod
    def categories(cls) -> frozenset[ToolCategory]:
        return frozenset(registration.category for registration in cls.all_registered().values())

    @classmethod
    def capabilities(cls) -> frozenset[ToolCapability]:
        result: set[ToolCapability] = set()
        for registration in cls.all_registered().values():
            result.update(registration.capabilities)
        return frozenset(result)

    @classmethod
    def all_registrations(cls) -> dict[str, ToolRegistration]:
        """Return a copy of the registry - mutating the returned dict
        never affects what's actually registered."""
        return cls.all_registered()
