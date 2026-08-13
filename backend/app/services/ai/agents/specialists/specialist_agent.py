"""SpecialistAgent - the abstract contract every specialist (Research
today; Finance/Trading/Vision/Legal/Marketing/Product/Coding in future
milestones) implements, extending BaseAgent.

Not named in the milestone's literal file list, but required by its
"Create a SpecialistAgent ABC extending BaseAgent" instruction - added as
its own module for the same reason app.services.ai.agents.base_agent.py
holds BaseAgent: the contract every concrete implementation depends on
needs one unambiguous home, not buried inside an __init__.py or a
same-named sibling module.

Every member BaseAgent already declares abstract (execute(), capabilities(),
...) is not re-declared here - it is already required. The six genuinely
new abstract members below are what distinguishes "a specialist" from any
other agent: it has a stable specialization() identifier, declares which
SpecialistTaskTypes it supports, can plan() and evaluate() its own work in
specialist-specific terms, and separates self_check() (internal
consistency - are this specialist's own collaborators correctly wired)
from health_check() (external dependency health - are the systems it
calls into reachable) - both distinct from BaseAgent.health(), the
generic per-agent liveness signal every agent already exposes. A concrete
specialist's health() typically delegates to self.health_check().
"""

from abc import abstractmethod
from typing import Any

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.response import SpecialistResponse
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType


class SpecialistAgent(BaseAgent):
    @abstractmethod
    def specialization(self) -> str:
        """A short, stable identifier for what this specialist does (e.g.
        "research"). Distinct from identity.name/agent_id - a
        specialization can be shared by multiple differently-configured
        instances of the same specialist type."""
        raise NotImplementedError

    @abstractmethod
    def supported_tasks(self) -> frozenset[SpecialistTaskType]:
        raise NotImplementedError

    @abstractmethod
    def plan(self, context: SpecialistContext) -> Any:
        """Produce this specialist's plan for the given context -
        typically delegating to self.planner().plan(context)."""
        raise NotImplementedError

    @abstractmethod
    def evaluate(self, response: SpecialistResponse) -> bool:
        """Assess whether a response actually satisfies its originating
        request - a specialist-specific quality gate, distinct from
        AgentPlanner.evaluate() (which assesses a *plan*, not a response)."""
        raise NotImplementedError

    @abstractmethod
    def self_check(self) -> bool:
        """Internal consistency check - are this specialist's own
        collaborators (planner, adapters, ...) correctly wired. No
        external I/O; contrast with health_check()."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        """External dependency health - are the systems this specialist
        calls into (memory, tools, runtime) reachable. Distinct from
        BaseAgent.health(), which concrete specialists typically implement
        by delegating to this method."""
        raise NotImplementedError
