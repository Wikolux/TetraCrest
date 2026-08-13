"""ResearchPlanner - a deterministic, rule-based planner. No LLM
reasoning, no chain-of-thought: given a request, it produces a fixed,
predictable sequence of SpecialistTasks based only on simple, objective
facts about the request (does it have constraints to verify) - never by
analyzing the meaning of the objective text itself. Matches the same
determinism ExecutivePlanner (app.services.ai.agents.executive.planner)
already established for the Executive's own planning.
"""

from app.services.ai.agents.specialists.planner import SpecialistPlan, SpecialistPlanner
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.task import SpecialistTask, SpecialistTaskType


class ResearchPlanner(SpecialistPlanner):
    def plan(self, context: SpecialistContext) -> SpecialistPlan:
        request = context.request
        objective = request.objective if request is not None else ""

        tasks = [
            SpecialistTask(
                task_type=SpecialistTaskType.RESEARCH, title="Gather information", description=objective
            )
        ]

        if request is not None and request.constraints:
            tasks.append(
                SpecialistTask(task_type=SpecialistTaskType.VERIFICATION, title="Verify against constraints")
            )

        tasks.append(SpecialistTask(task_type=SpecialistTaskType.ANALYSIS, title="Analyze findings"))
        tasks.append(SpecialistTask(task_type=SpecialistTaskType.SUMMARIZATION, title="Summarize findings"))

        return tuple(tasks)

    def replan(self, context: SpecialistContext, previous_plan: SpecialistPlan) -> SpecialistPlan:
        """No adaptive replanning logic exists yet (no LLM reasoning to
        drive it) - replanning simply produces a fresh deterministic plan
        from the current context."""
        return self.plan(context)

    def evaluate(self, context: SpecialistContext, plan: SpecialistPlan) -> bool:
        return len(plan) > 0

    def next_step(self, context: SpecialistContext, plan: SpecialistPlan) -> SpecialistTask | None:
        return plan[0] if plan else None
