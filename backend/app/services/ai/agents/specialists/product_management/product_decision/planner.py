"""DecisionPlanner - a deterministic, rule-based planner implementing
SpecialistPlanner, mirroring DiscoveryPlanner's own precedent exactly.
Every task is tagged SpecialistTaskType.COMPARISON - the category ARR §3
names as this specialist's own fit ("COMPARISON (SpecialistTaskType, for
tradeoff work)") - with the operation's real purpose carried in the
task's title. The plan is an observability artifact, not a step-by-step
execution driver - the specialist's own code does the actual work.
"""

from app.services.ai.agents.specialists.planner import SpecialistPlan, SpecialistPlanner
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.task import SpecialistTask, SpecialistTaskType

TASK_GATHER_PRECEDENT = "Gather decision precedent and evidence"
TASK_PROCESS_REQUEST = "Process product decision request"


class DecisionPlanner(SpecialistPlanner):
    def plan(self, context: SpecialistContext) -> SpecialistPlan:
        return (
            SpecialistTask(task_type=SpecialistTaskType.COMPARISON, title=TASK_GATHER_PRECEDENT),
            SpecialistTask(task_type=SpecialistTaskType.COMPARISON, title=TASK_PROCESS_REQUEST),
        )

    def replan(self, context: SpecialistContext, previous_plan: SpecialistPlan) -> SpecialistPlan:
        return self.plan(context)

    def evaluate(self, context: SpecialistContext, plan: SpecialistPlan) -> bool:
        return len(plan) > 0

    def next_step(self, context: SpecialistContext, plan: SpecialistPlan) -> SpecialistTask | None:
        return plan[0] if plan else None
