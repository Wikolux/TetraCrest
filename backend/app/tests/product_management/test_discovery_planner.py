"""DiscoveryPlanner - mirrors test_research_planner.py's own coverage: a
deterministic, non-empty plan, tagged with the closed SpecialistTaskType
taxonomy (never a new member), evaluable and re-plannable without
adaptive behaviour.
"""

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.product_management.discovery.planner import DiscoveryPlanner
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType


def _context() -> SpecialistContext:
    return SpecialistContext(agent_context=AgentContext(organization_id=1))


def test_plan_is_non_empty():
    planner = DiscoveryPlanner()
    plan = planner.plan(_context())
    assert len(plan) > 0


def test_plan_tasks_use_investigation_task_type():
    planner = DiscoveryPlanner()
    plan = planner.plan(_context())
    assert all(task.task_type == SpecialistTaskType.INVESTIGATION for task in plan)


def test_replan_matches_plan_deterministically():
    planner = DiscoveryPlanner()
    context = _context()
    first = planner.plan(context)
    second = planner.replan(context, first)
    assert [task.title for task in first] == [task.title for task in second]


def test_evaluate_true_for_non_empty_plan():
    planner = DiscoveryPlanner()
    plan = planner.plan(_context())
    assert planner.evaluate(_context(), plan) is True


def test_evaluate_false_for_empty_plan():
    planner = DiscoveryPlanner()
    assert planner.evaluate(_context(), ()) is False


def test_next_step_returns_first_task():
    planner = DiscoveryPlanner()
    plan = planner.plan(_context())
    assert planner.next_step(_context(), plan) == plan[0]


def test_next_step_returns_none_for_empty_plan():
    planner = DiscoveryPlanner()
    assert planner.next_step(_context(), ()) is None
