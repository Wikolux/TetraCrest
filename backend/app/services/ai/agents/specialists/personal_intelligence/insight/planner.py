"""InsightPlanner - a deterministic, rule-based planner implementing
SpecialistPlanner (reusing the existing abstraction, exactly like
PersonalIntelligencePlanner/ResearchPlanner - never inventing a parallel
one).

Unlike PersonalIntelligencePlanner (whose write-only operations don't fit
any closed SpecialistTaskType member and fall back to UNKNOWN), insight
generation genuinely fits the existing taxonomy: detecting patterns/
habits/contradictions/alignment is ANALYSIS, and producing a periodic
reflection/recommendation set/profile update from already-detected
insights is SUMMARIZATION. No new SpecialistTaskType member is needed.

As with every other specialist planner in this platform, this plan is an
observability artifact, not a step-by-step execution driver - InsightAgent's
own process() method, not a generic task executor, does the actual work.
"""

from app.services.ai.agents.specialists.planner import SpecialistPlan, SpecialistPlanner
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.task import SpecialistTask, SpecialistTaskType

TASK_GATHER_CORPUS = "Gather memory corpus for analysis"
TASK_DETECT_SIGNALS = "Detect patterns, habits, contradictions, and alignment"
TASK_SYNTHESIZE_INSIGHTS = "Synthesize insights and recommendations"


class InsightPlanner(SpecialistPlanner):
    def plan(self, context: SpecialistContext) -> SpecialistPlan:
        return (
            SpecialistTask(task_type=SpecialistTaskType.ANALYSIS, title=TASK_GATHER_CORPUS),
            SpecialistTask(task_type=SpecialistTaskType.ANALYSIS, title=TASK_DETECT_SIGNALS),
            SpecialistTask(task_type=SpecialistTaskType.SUMMARIZATION, title=TASK_SYNTHESIZE_INSIGHTS),
        )

    def replan(self, context: SpecialistContext, previous_plan: SpecialistPlan) -> SpecialistPlan:
        """No adaptive replanning logic exists yet - matches every other
        deterministic planner in this platform."""
        return self.plan(context)

    def evaluate(self, context: SpecialistContext, plan: SpecialistPlan) -> bool:
        return len(plan) > 0

    def next_step(self, context: SpecialistContext, plan: SpecialistPlan) -> SpecialistTask | None:
        return plan[0] if plan else None
