from app.services.ai.agents.specialists.registry import SpecialistRegistry
from app.services.ai.agents.specialists.specialist_agent import SpecialistAgent
from app.services.ai.agents.types import AgentError


class SpecialistFactory:
    """Resolves a specialist name into a constructed SpecialistAgent via
    SpecialistRegistry. Nothing else - mirrors AgentFactory/ToolFactory
    exactly.
    """

    @staticmethod
    def create(name: str, *args, **kwargs) -> SpecialistAgent:
        specialist_class = SpecialistRegistry.get(name)
        if specialist_class is None:
            raise AgentError(f"Unknown specialist: {name}")
        return specialist_class(*args, **kwargs)

    @staticmethod
    def exists(name: str) -> bool:
        return SpecialistRegistry.exists(name)

    @staticmethod
    def available() -> tuple[str, ...]:
        return SpecialistRegistry.available()
