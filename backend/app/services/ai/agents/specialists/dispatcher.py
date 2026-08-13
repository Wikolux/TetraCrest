"""SpecialistDispatcher - matches a SpecialistTaskType or specialization
name to a registered specialist, purely from SpecialistRegistry's
registration-time metadata. Never instantiates a candidate to answer a
routing question, and never contains a hardcoded `if task == "research"`
branch - adding a new specialist (Finance, Trading, Vision, ...) only
requires it to register itself with the right supported_tasks; this file
never changes (Open/Closed).

Returns a specialist *name* (str), not an instance - the caller
(typically the Executive, via SpecialistFactory) constructs it. This is a
strict improvement over app.services.ai.agents.executive.dispatcher.Dispatcher,
which had to hold actual agent instances to match by capability since
AgentRegistry never captured that metadata at registration time.
"""

from app.services.ai.agents.specialists.registry import SpecialistRegistry
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType


class SpecialistDispatcher:
    def __init__(self, registry: type[SpecialistRegistry] = SpecialistRegistry) -> None:
        self.registry = registry

    def dispatch_by_task_type(self, task_type: SpecialistTaskType) -> str | None:
        for name, registration in self.registry.all_registrations().items():
            if task_type in registration.supported_tasks:
                return name
        return None

    def dispatch_by_specialization(self, specialization: str) -> str | None:
        for name, registration in self.registry.all_registrations().items():
            if registration.specialization == specialization:
                return name
        return None
