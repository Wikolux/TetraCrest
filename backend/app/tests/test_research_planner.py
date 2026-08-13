from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.planner import SpecialistPlanner
from app.services.ai.agents.specialists.research.context import build_research_context
from app.services.ai.agents.specialists.research.planner import ResearchPlanner
from app.services.ai.agents.specialists.shared.request import SpecialistRequest
from app.services.ai.agents.specialists.shared.task import SpecialistTask, SpecialistTaskType


def _context(**overrides):
    request = SpecialistRequest(objective="Prepare for an interview", **overrides)
    return build_research_context(AgentContext(organization_id=1), request)


def test_research_planner_is_a_specialist_planner():
    assert isinstance(ResearchPlanner(), SpecialistPlanner)


def test_plan_returns_only_specialist_tasks_never_plain_strings():
    plan = ResearchPlanner().plan(_context())

    assert all(isinstance(task, SpecialistTask) for task in plan)


def test_plan_always_includes_a_research_task_first():
    plan = ResearchPlanner().plan(_context())

    assert plan[0].task_type == SpecialistTaskType.RESEARCH
    assert plan[0].title == "Gather information"


def test_plan_without_constraints_skips_the_verification_task():
    plan = ResearchPlanner().plan(_context())

    assert SpecialistTaskType.VERIFICATION not in [task.task_type for task in plan]


def test_plan_with_constraints_includes_a_verification_task():
    plan = ResearchPlanner().plan(_context(constraints=("must cite sources",)))

    assert SpecialistTaskType.VERIFICATION in [task.task_type for task in plan]


def test_plan_always_ends_with_analysis_then_summarization():
    plan = ResearchPlanner().plan(_context())

    assert [task.task_type for task in plan[-2:]] == [SpecialistTaskType.ANALYSIS, SpecialistTaskType.SUMMARIZATION]


def test_plan_is_deterministic_regardless_of_objective_content():
    first_plan = ResearchPlanner().plan(_context())
    second = build_research_context(
        AgentContext(organization_id=1), SpecialistRequest(objective="Totally different objective")
    )
    second_plan = ResearchPlanner().plan(second)

    assert [task.task_type for task in first_plan] == [task.task_type for task in second_plan]


def test_replan_produces_an_equivalent_fresh_plan():
    planner = ResearchPlanner()
    context = _context()
    plan = planner.plan(context)

    replanned = planner.replan(context, plan)

    assert [task.task_type for task in replanned] == [task.task_type for task in plan]


def test_evaluate_is_true_for_a_non_empty_plan():
    planner = ResearchPlanner()

    assert planner.evaluate(_context(), planner.plan(_context())) is True


def test_evaluate_is_false_for_an_empty_plan():
    assert ResearchPlanner().evaluate(_context(), ()) is False


def test_next_step_returns_the_first_task():
    planner = ResearchPlanner()
    plan = planner.plan(_context())

    assert planner.next_step(_context(), plan) is plan[0]


def test_next_step_returns_none_for_an_empty_plan():
    assert ResearchPlanner().next_step(_context(), ()) is None


def test_plan_handles_a_context_with_no_request():
    from app.services.ai.agents.specialists.shared.context import SpecialistContext

    context = SpecialistContext(agent_context=AgentContext(organization_id=1))

    plan = ResearchPlanner().plan(context)

    assert len(plan) >= 1
