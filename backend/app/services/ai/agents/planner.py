"""AgentPlanner - the abstraction an agent uses to decide what to do.

Deliberately no reasoning implementation - only the interface. A plan's
actual shape is intentionally left as Any: this milestone has no opinion
about what a "plan" looks like (a list of steps, a graph, a single next
action, ...), only that planning happens through this contract.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.services.ai.agents.context import AgentContext


class AgentPlanner(ABC):
    @abstractmethod
    def plan(self, context: AgentContext) -> Any:
        """Produce a plan for the given context."""
        raise NotImplementedError

    @abstractmethod
    def replan(self, context: AgentContext, previous_plan: Any) -> Any:
        """Produce a revised plan given a previous one that no longer holds."""
        raise NotImplementedError

    @abstractmethod
    def evaluate(self, context: AgentContext, plan: Any) -> Any:
        """Assess how well a plan is doing (or did)."""
        raise NotImplementedError

    @abstractmethod
    def next_step(self, context: AgentContext, plan: Any) -> Any:
        """Return the next step of a plan that should be executed."""
        raise NotImplementedError
