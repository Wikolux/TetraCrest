"""SpecialistRegistry - maps a specialist name to a registered specialist
class plus the declared metadata (specialization, supported_tasks) needed
for routing, all supplied at registration time.

Declaring specialization/supported_tasks as part of register() rather
than deriving them by instantiating the specialist class is the same
architectural improvement made for app.services.ai.tools.registry.ToolRegistry
in the Tool Framework milestone, applied here: specialization()/
supported_tasks() are abstract *instance* properties/methods (each
concrete specialist decides its own), so a registry holding only classes
can't answer "what does this specialist handle" without constructing one
- and specialist constructors are not standardized on one shape. Requiring
this metadata once at registration - exactly when a specialist already
knows its own identity - means SpecialistDispatcher works directly off
the registry, with no instantiation needed anywhere in routing.

Built on GenericProviderRegistry (app.services.ai.shared.provider_registry),
the same base AgentRegistry/ToolRegistry use: class-level shared state,
guarded by a re-entrant lock, duplicate registration rejected unless
overwrite=True. Specialists self-register; nothing here or in
SpecialistFactory needs modification when a new specialist is added
(Open/Closed). register()/get() are overridden for the same reason as
ToolRegistry: a SpecialistRegistration (class plus specialization/
supported_tasks) is stored under the name, not the bare class.
"""

from dataclasses import dataclass, field

from app.services.ai.agents.specialists.shared.task import SpecialistTaskType
from app.services.ai.agents.specialists.specialist_agent import SpecialistAgent
from app.services.ai.agents.types import AgentError
from app.services.ai.shared.provider_registry import GenericProviderRegistry


@dataclass(frozen=True)
class SpecialistRegistration:
    specialist_class: type[SpecialistAgent]
    specialization: str
    supported_tasks: frozenset[SpecialistTaskType] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not isinstance(self.supported_tasks, frozenset):
            object.__setattr__(self, "supported_tasks", frozenset(self.supported_tasks))


class SpecialistRegistry(GenericProviderRegistry[str, SpecialistRegistration]):
    _registration_error = AgentError

    @classmethod
    def register(
        cls,
        name: str,
        specialist_class: type[SpecialistAgent],
        *,
        specialization: str,
        supported_tasks: frozenset[SpecialistTaskType] = frozenset(),
        overwrite: bool = False,
    ) -> None:
        registration = SpecialistRegistration(
            specialist_class=specialist_class,
            specialization=specialization,
            supported_tasks=frozenset(supported_tasks),
        )
        super().register(name, registration, overwrite=overwrite)

    @classmethod
    def exists(cls, name: str) -> bool:
        return cls.is_registered(name)

    @classmethod
    def get(cls, name: str) -> type[SpecialistAgent] | None:
        registration = super().get(name)
        return registration.specialist_class if registration else None

    @classmethod
    def get_registration(cls, name: str) -> SpecialistRegistration | None:
        return super().get(name)

    @classmethod
    def available(cls) -> tuple[str, ...]:
        return tuple(cls.all_registered().keys())

    @classmethod
    def specializations(cls) -> frozenset[str]:
        return frozenset(registration.specialization for registration in cls.all_registered().values())

    @classmethod
    def all_registrations(cls) -> dict[str, SpecialistRegistration]:
        """Return a copy of the registry - mutating the returned dict
        never affects what's actually registered."""
        return cls.all_registered()
