"""PersonalIntelligencePlanner - a deterministic, rule-based planner,
implementing SpecialistPlanner (reusing the existing abstraction rather
than inventing a parallel one, exactly like ResearchPlanner).

Personal Intelligence's operations (remember an identity fact, remember a
goal, recall context, ...) don't map onto SpecialistTaskType's existing
closed taxonomy (RESEARCH/ANALYSIS/SUMMARIZATION/COMPARISON/VERIFICATION/
INVESTIGATION) - none of them fit, and SpecialistTaskType must not be
modified (it is a frozen, shared platform type; the task.py module's own
docstring already provides UNKNOWN "for tasks that don't fit yet"). Every
task this planner produces is therefore SpecialistTaskType.UNKNOWN, with
its real, human-readable purpose carried in the task's title - the same
"the plan is an observability artifact, not a step-by-step execution
driver" role SpecialistTask plays for ResearchAgent (see
ResearchAgent.research(): the plan is counted/emitted, but the specialist's
own code - not a generic task executor - does the actual work).
"""

from app.services.ai.agents.specialists.planner import SpecialistPlan, SpecialistPlanner
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.task import SpecialistTask, SpecialistTaskType

TASK_RETRIEVE_CONTEXT = "Retrieve relevant personal context"
TASK_PROCESS_REQUEST = "Process personal intelligence request"


class PersonalIntelligencePlanner(SpecialistPlanner):
    def plan(self, context: SpecialistContext) -> SpecialistPlan:
        return (
            SpecialistTask(task_type=SpecialistTaskType.UNKNOWN, title=TASK_RETRIEVE_CONTEXT),
            SpecialistTask(task_type=SpecialistTaskType.UNKNOWN, title=TASK_PROCESS_REQUEST),
        )

    def replan(self, context: SpecialistContext, previous_plan: SpecialistPlan) -> SpecialistPlan:
        """No adaptive replanning logic exists yet - matches every other
        deterministic planner in this platform (ExecutivePlanner,
        ResearchPlanner)."""
        return self.plan(context)

    def evaluate(self, context: SpecialistContext, plan: SpecialistPlan) -> bool:
        return len(plan) > 0

    def next_step(self, context: SpecialistContext, plan: SpecialistPlan) -> SpecialistTask | None:
        return plan[0] if plan else None
