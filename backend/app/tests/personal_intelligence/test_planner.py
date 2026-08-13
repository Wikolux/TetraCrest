"""PersonalIntelligencePlanner - a deterministic, fixed two-task plan.
Every task is SpecialistTaskType.UNKNOWN by design (see planner.py's own
docstring for why none of the closed SpecialistTaskType members fit).
"""

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.personal_intelligence.context import build_personal_intelligence_context
from app.services.ai.agents.specialists.personal_intelligence.planner import (
    TASK_PROCESS_REQUEST,
    TASK_RETRIEVE_CONTEXT,
    PersonalIntelligencePlanner,
)
from app.services.ai.agents.specialists.planner import SpecialistPlanner
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType


def _context():
    return build_personal_intelligence_context(AgentContext(organization_id=1), None)


def test_is_a_specialist_planner():
    assert isinstance(PersonalIntelligencePlanner(), SpecialistPlanner)


def test_plan_returns_exactly_two_tasks():
    plan = PersonalIntelligencePlanner().plan(_context())
    assert len(plan) == 2


def test_every_task_is_unknown_typed():
    plan = PersonalIntelligencePlanner().plan(_context())
    assert all(task.task_type == SpecialistTaskType.UNKNOWN for task in plan)


def test_task_titles_match_the_documented_constants():
    plan = PersonalIntelligencePlanner().plan(_context())
    titles = [task.title for task in plan]
    assert titles == [TASK_RETRIEVE_CONTEXT, TASK_PROCESS_REQUEST]


def test_plan_is_deterministic_across_calls():
    # SpecialistTask.task_id is freshly generated per call, so plans are
    # compared by (task_type, title) - the deterministic, meaningful part -
    # not by full dataclass equality.
    planner = PersonalIntelligencePlanner()
    first = [(task.task_type, task.title) for task in planner.plan(_context())]
    second = [(task.task_type, task.title) for task in planner.plan(_context())]
    assert first == second


def test_replan_returns_the_same_fixed_plan():
    planner = PersonalIntelligencePlanner()
    original = planner.plan(_context())
    replanned = planner.replan(_context(), original)
    assert [(t.task_type, t.title) for t in replanned] == [(t.task_type, t.title) for t in original]


def test_evaluate_is_true_for_a_non_empty_plan():
    planner = PersonalIntelligencePlanner()
    assert planner.evaluate(_context(), planner.plan(_context())) is True


def test_evaluate_is_false_for_an_empty_plan():
    assert PersonalIntelligencePlanner().evaluate(_context(), ()) is False


def test_next_step_returns_the_first_task():
    planner = PersonalIntelligencePlanner()
    plan = planner.plan(_context())
    assert planner.next_step(_context(), plan) is plan[0]


def test_next_step_returns_none_for_an_empty_plan():
    assert PersonalIntelligencePlanner().next_step(_context(), ()) is None
