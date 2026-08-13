"""BaseAgent - the abstract contract every intelligent entity in the AI
Operating System derives from.

An Agent is not a provider, not a runtime, not a prompt - it is an
autonomous execution unit, the operating-system-process analogue: the
Runtime executes, the Agent decides. Every method below is abstract, with
no concrete default, matching the milestone's explicit "every future
agent must implement these" - there is no generically-correct behavior
for any of them to fall back to, the same reasoning that keeps
ConversationProvider.generate()/health_check()/provider_name/model_name
abstract while its more optional members get safe defaults.

identity and state_machine are concrete, constructor-provided
infrastructure rather than abstract members - every agent needs both
wired up correctly, and there's nothing agent-specific about *how* they're
wired, only reused.
"""

from abc import ABC, abstractmethod

from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentState
from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.planner import AgentPlanner
from app.services.ai.agents.state import AgentStateMachine
from app.services.ai.agents.types import AgentIdentity
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeResponse


class BaseAgent(ABC):
    def __init__(self, identity: AgentIdentity, state_machine: AgentStateMachine | None = None) -> None:
        self.identity = identity
        self.state_machine = state_machine or AgentStateMachine()

    @property
    def state(self) -> AgentState:
        return self.state_machine.state

    @abstractmethod
    def initialize(self) -> None:
        """Perform setup required before this agent can run."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, context: AgentContext) -> RuntimeResponse:
        """Do this agent's actual work for one execution, always through
        self.runtime() - never by calling a provider directly."""
        raise NotImplementedError

    @abstractmethod
    def pause(self) -> None:
        """Suspend this agent, expected to be resumable later."""
        raise NotImplementedError

    @abstractmethod
    def resume(self) -> None:
        """Resume a previously paused agent."""
        raise NotImplementedError

    @abstractmethod
    def cancel(self) -> None:
        """Stop this agent's current execution; not resumable."""
        raise NotImplementedError

    @abstractmethod
    def shutdown(self) -> None:
        """Release whatever initialize() acquired."""
        raise NotImplementedError

    @abstractmethod
    def health(self) -> bool:
        """Return whether this agent is currently able to serve requests."""
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> AgentCapabilities:
        """Return what this agent declares it supports."""
        raise NotImplementedError

    @abstractmethod
    def permissions(self) -> tuple[str, ...]:
        """Return the permissions this agent has been granted."""
        raise NotImplementedError

    @abstractmethod
    def memory(self) -> AgentMemory | None:
        """Return this agent's memory abstraction, or None if it has none."""
        raise NotImplementedError

    @abstractmethod
    def planner(self) -> AgentPlanner | None:
        """Return this agent's planner abstraction, or None if it has none."""
        raise NotImplementedError

    @abstractmethod
    def runtime(self) -> AIRuntime:
        """Return the AIRuntime this agent executes through."""
        raise NotImplementedError
