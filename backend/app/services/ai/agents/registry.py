from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.types import AgentError
from app.services.ai.shared.provider_registry import GenericProviderRegistry


class AgentRegistry(GenericProviderRegistry[str, type[BaseAgent]]):
    """Maps an agent name to a concrete BaseAgent class.

    Built on GenericProviderRegistry (app.services.ai.shared.provider_registry),
    the same base ConversationProviderRegistry/ToolRegistry/SpecialistRegistry
    use: class-level shared state, guarded by a re-entrant lock, duplicate
    registration rejected unless overwrite=True is passed explicitly. Agents
    self-register under their own name; AgentFactory never needs to change
    when a new agent is added.
    """

    _registration_error = AgentError
