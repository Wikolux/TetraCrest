"""AgentOrchestrator - the interface a future Executive/Orchestrator layer
will implement to coordinate multiple agents. No orchestration logic
exists here, only the contract.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.messages import AgentMessage
from app.services.ai.agents.types import AgentExecutionResult


class AgentOrchestrator(ABC):
    @abstractmethod
    def dispatch(self, agent: BaseAgent, context: AgentContext) -> AgentExecutionResult:
        """Run one agent for one context."""
        raise NotImplementedError

    @abstractmethod
    def delegate(self, from_agent: BaseAgent, to_agent: BaseAgent, message: AgentMessage) -> Any:
        """Hand work from one agent to another."""
        raise NotImplementedError

    @abstractmethod
    def synchronize(self, agents: tuple[BaseAgent, ...]) -> Any:
        """Coordinate a group of agents so their state/results converge."""
        raise NotImplementedError

    @abstractmethod
    def terminate(self, agent: BaseAgent) -> None:
        """Stop an agent under this orchestrator's supervision."""
        raise NotImplementedError
