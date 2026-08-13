"""CommunicationPlanner - a deterministic, rule-based planner implementing
SpecialistPlanner, mirroring DiscoveryPlanner/DecisionPlanner/DeliveryPlanner/
StrategyPlanner exactly. Every task is tagged SpecialistTaskType.SUMMARIZATION
- the category ARR §3 names as this specialist's own fit - with the
operation's real purpose carried in the task's title. The plan is an
observability artifact, not a step-by-step execution driver.
"""

from app.services.ai.agents.specialists.planner import SpecialistPlan, SpecialistPlanner
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.task import SpecialistTask, SpecialistTaskType

TASK_GATHER_PRECEDENT = "Gather product knowledge and stakeholder context"
TASK_PROCESS_REQUEST = "Process stakeholder communication request"


class CommunicationPlanner(SpecialistPlanner):
    def plan(self, context: SpecialistContext) -> SpecialistPlan:
        return (
            SpecialistTask(task_type=SpecialistTaskType.SUMMARIZATION, title=TASK_GATHER_PRECEDENT),
            SpecialistTask(task_type=SpecialistTaskType.SUMMARIZATION, title=TASK_PROCESS_REQUEST),
        )

    def replan(self, context: SpecialistContext, previous_plan: SpecialistPlan) -> SpecialistPlan:
        return self.plan(context)

    def evaluate(self, context: SpecialistContext, plan: SpecialistPlan) -> bool:
        return len(plan) > 0

    def next_step(self, context: SpecialistContext, plan: SpecialistPlan) -> SpecialistTask | None:
        return plan[0] if plan else None
