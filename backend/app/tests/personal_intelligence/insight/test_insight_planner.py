"""InsightPlanner - a deterministic, fixed three-task plan. Unlike
PersonalIntelligencePlanner, insight generation genuinely fits the
existing SpecialistTaskType taxonomy (ANALYSIS/SUMMARIZATION) rather than
falling back to UNKNOWN.
"""

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.personal_intelligence.insight.context import build_insight_context
from app.services.ai.agents.specialists.personal_intelligence.insight.planner import (
    TASK_DETECT_SIGNALS,
    TASK_GATHER_CORPUS,
    TASK_SYNTHESIZE_INSIGHTS,
    InsightPlanner,
)
from app.services.ai.agents.specialists.planner import SpecialistPlanner
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType


def _context():
    return build_insight_context(AgentContext(organization_id=1), None)


def test_is_a_specialist_planner():
    assert isinstance(InsightPlanner(), SpecialistPlanner)


def test_plan_returns_exactly_three_tasks():
    assert len(InsightPlanner().plan(_context())) == 3


def test_gathering_and_detection_tasks_are_analysis_typed():
    plan = InsightPlanner().plan(_context())
    assert plan[0].task_type == SpecialistTaskType.ANALYSIS
    assert plan[1].task_type == SpecialistTaskType.ANALYSIS


def test_synthesis_task_is_summarization_typed():
    plan = InsightPlanner().plan(_context())
    assert plan[2].task_type == SpecialistTaskType.SUMMARIZATION


def test_task_titles_match_the_documented_constants():
    plan = InsightPlanner().plan(_context())
    assert [task.title for task in plan] == [TASK_GATHER_CORPUS, TASK_DETECT_SIGNALS, TASK_SYNTHESIZE_INSIGHTS]


def test_plan_is_deterministic_across_calls():
    planner = InsightPlanner()
    first = [(t.task_type, t.title) for t in planner.plan(_context())]
    second = [(t.task_type, t.title) for t in planner.plan(_context())]
    assert first == second


def test_replan_returns_the_same_fixed_plan():
    planner = InsightPlanner()
    original = planner.plan(_context())
    replanned = planner.replan(_context(), original)
    assert [(t.task_type, t.title) for t in replanned] == [(t.task_type, t.title) for t in original]


def test_evaluate_is_true_for_a_non_empty_plan():
    planner = InsightPlanner()
    assert planner.evaluate(_context(), planner.plan(_context())) is True


def test_evaluate_is_false_for_an_empty_plan():
    assert InsightPlanner().evaluate(_context(), ()) is False


def test_next_step_returns_the_first_task():
    planner = InsightPlanner()
    plan = planner.plan(_context())
    assert planner.next_step(_context(), plan) is plan[0]


def test_next_step_returns_none_for_an_empty_plan():
    assert InsightPlanner().next_step(_context(), ()) is None
