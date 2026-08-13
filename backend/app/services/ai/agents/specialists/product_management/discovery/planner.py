"""DiscoveryPlanner - a deterministic, rule-based planner implementing
SpecialistPlanner (reusing the existing abstraction, exactly like
ResearchPlanner/PersonalIntelligencePlanner - never a parallel one).

Discovery's operations don't map onto SpecialistTaskType's existing closed
taxonomy any more precisely than one shared category - every task this
planner produces is tagged SpecialistTaskType.INVESTIGATION (the category
ARR §3/Architecture §19 name as Discovery's own fit), with the operation's
real, human-readable purpose carried in the task's title. The plan is an
observability artifact here too (see ResearchPlanner's own docstring) -
DiscoverySpecialist's own code, not a generic task executor, does the
actual work.
"""

from app.services.ai.agents.specialists.planner import SpecialistPlan, SpecialistPlanner
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.task import SpecialistTask, SpecialistTaskType

TASK_GATHER_PRECEDENT = "Gather product and precedent context"
TASK_PROCESS_REQUEST = "Process discovery request"


class DiscoveryPlanner(SpecialistPlanner):
    def plan(self, context: SpecialistContext) -> SpecialistPlan:
        return (
            SpecialistTask(task_type=SpecialistTaskType.INVESTIGATION, title=TASK_GATHER_PRECEDENT),
            SpecialistTask(task_type=SpecialistTaskType.INVESTIGATION, title=TASK_PROCESS_REQUEST),
        )

    def replan(self, context: SpecialistContext, previous_plan: SpecialistPlan) -> SpecialistPlan:
        """No adaptive replanning logic exists yet - matches every other
        deterministic planner in this platform (ExecutivePlanner,
        ResearchPlanner, PersonalIntelligencePlanner)."""
        return self.plan(context)

    def evaluate(self, context: SpecialistContext, plan: SpecialistPlan) -> bool:
        return len(plan) > 0

    def next_step(self, context: SpecialistContext, plan: SpecialistPlan) -> SpecialistTask | None:
        return plan[0] if plan else None
