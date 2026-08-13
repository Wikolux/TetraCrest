"""SpecialistPlanner - the base contract every specialist's own planner
(ResearchPlanner today) implements, narrowing AgentPlanner's generic
Any-typed members to the specialist-specific shapes (SpecialistContext in,
a plan of SpecialistTasks out) - reusing AgentPlanner
(app.services.ai.agents.planner) rather than inventing a parallel
planning abstraction.

Purely a typing/documentation narrowing: AgentPlanner's four methods are
already abstract, so nothing new is required here at the Python level:
subclassing without overriding keeps every method abstract automatically.
The abstract re-declarations below exist only so every specialist planner
that inherits from this class - rather than AgentPlanner directly - gets
IDE/type-checker-visible, specialist-shaped signatures.
"""

from abc import abstractmethod

from app.services.ai.agents.planner import AgentPlanner
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.task import SpecialistTask

SpecialistPlan = tuple[SpecialistTask, ...]


class SpecialistPlanner(AgentPlanner):
    @abstractmethod
    def plan(self, context: SpecialistContext) -> SpecialistPlan:
        raise NotImplementedError

    @abstractmethod
    def replan(self, context: SpecialistContext, previous_plan: SpecialistPlan) -> SpecialistPlan:
        raise NotImplementedError

    @abstractmethod
    def evaluate(self, context: SpecialistContext, plan: SpecialistPlan) -> bool:
        raise NotImplementedError

    @abstractmethod
    def next_step(self, context: SpecialistContext, plan: SpecialistPlan) -> SpecialistTask | None:
        raise NotImplementedError
