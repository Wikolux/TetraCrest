"""CommunicationPlanner - mirrors every prior milestone's own coverage."""

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.product_management.stakeholder_communication.planner import CommunicationPlanner
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType


def _context() -> SpecialistContext:
    return SpecialistContext(agent_context=AgentContext(organization_id=1))


def test_plan_is_non_empty():
    assert len(CommunicationPlanner().plan(_context())) > 0


def test_plan_tasks_use_summarization_task_type():
    plan = CommunicationPlanner().plan(_context())
    assert all(task.task_type == SpecialistTaskType.SUMMARIZATION for task in plan)


def test_replan_matches_plan_deterministically():
    planner = CommunicationPlanner()
    context = _context()
    first = planner.plan(context)
    second = planner.replan(context, first)
    assert [task.title for task in first] == [task.title for task in second]


def test_evaluate_true_for_non_empty_plan_false_for_empty():
    planner = CommunicationPlanner()
    assert planner.evaluate(_context(), planner.plan(_context())) is True
    assert planner.evaluate(_context(), ()) is False


def test_next_step_returns_first_task_or_none():
    planner = CommunicationPlanner()
    plan = planner.plan(_context())
    assert planner.next_step(_context(), plan) == plan[0]
    assert planner.next_step(_context(), ()) is None
