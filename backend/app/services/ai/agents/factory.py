from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.registry import AgentRegistry
from app.services.ai.agents.types import AgentError


class AgentFactory:
    """Resolves an agent name into a constructed BaseAgent via
    AgentRegistry. Nothing else - no lifecycle management, no execution,
    no policy enforcement; those belong to AgentLifecycle/AgentExecutor.

    create() forwards *args/**kwargs to the resolved class's constructor
    rather than a single typed config object: unlike a ConversationProvider
    (which is always built from one ConversationProviderConfig), a
    BaseAgent subclass's constructor needs are genuinely agent-specific
    (its own identity, runtime, memory, planner, ...), so there is no one
    shape a factory could standardize on here.
    """

    @staticmethod
    def create(name: str, *args, **kwargs) -> BaseAgent:
        agent_class = AgentRegistry.get(name)
        if agent_class is None:
            raise AgentError(f"Unknown agent: {name}")
        return agent_class(*args, **kwargs)

    @staticmethod
    def exists(name: str) -> bool:
        return AgentRegistry.is_registered(name)

    @staticmethod
    def available() -> tuple[str, ...]:
        return tuple(AgentRegistry.all_registered().keys())
