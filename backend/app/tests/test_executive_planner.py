from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.executive.context import ExecutiveContext
from app.services.ai.agents.executive.planner import (
    TASK_KIND_BUILD_CONTEXT,
    TASK_KIND_GENERATE_RESPONSE,
    TASK_KIND_RETRIEVE_CONVERSATIONS,
    TASK_KIND_RETRIEVE_MEMORY,
    TASK_KIND_RETURN_RESPONSE,
    ExecutivePlanner,
)
from app.services.ai.agents.executive.task import Task, TaskStatus
from app.services.ai.agents.executive.task_graph import TaskGraph
from app.services.ai.agents.planner import AgentPlanner


def _context(**overrides):
    agent_context = AgentContext(organization_id=1, **overrides)
    return ExecutiveContext(agent_context=agent_context, user_request="Help me prepare for an interview.")


def test_executive_planner_is_an_agent_planner():
    assert isinstance(ExecutivePlanner(), AgentPlanner)


def test_plan_returns_a_decision_and_a_task_graph():
    decision, graph = ExecutivePlanner().plan(_context())

    assert decision.requires_memory is True
    assert decision.requires_runtime is True
    assert isinstance(graph, TaskGraph)


def test_plan_never_returns_plain_strings_as_tasks():
    _, graph = ExecutivePlanner().plan(_context())

    for task in graph.all_tasks():
        assert isinstance(task, Task)


def test_plan_without_a_conversation_id_skips_the_conversation_retrieval_task():
    _, graph = ExecutivePlanner().plan(_context())

    titles = [task.title for task in graph.all_tasks()]
    assert "Retrieve previous conversations" not in titles
    assert "Retrieve memory" in titles


def test_plan_with_a_conversation_id_includes_the_conversation_retrieval_task():
    _, graph = ExecutivePlanner().plan(_context(conversation_id=7))

    titles = [task.title for task in graph.all_tasks()]
    assert "Retrieve previous conversations" in titles


def test_plan_matches_the_milestones_example_five_task_shape():
    _, graph = ExecutivePlanner().plan(_context(conversation_id=7))

    order = graph.execution_order()
    assert [task.title for task in order] == [
        "Retrieve memory",
        "Retrieve previous conversations",
        "Build prompt context",
        "Generate response",
        "Return response",
    ]


def test_build_context_task_depends_on_every_retrieval_task():
    _, graph = ExecutivePlanner().plan(_context(conversation_id=7))

    build_task = next(task for task in graph.all_tasks() if task.metadata["kind"] == TASK_KIND_BUILD_CONTEXT)
    retrieval_ids = {
        task.task_id
        for task in graph.all_tasks()
        if task.metadata["kind"] in (TASK_KIND_RETRIEVE_MEMORY, TASK_KIND_RETRIEVE_CONVERSATIONS)
    }

    assert set(build_task.dependencies) == retrieval_ids


def test_generate_response_task_depends_on_build_context():
    _, graph = ExecutivePlanner().plan(_context())

    build_task = next(task for task in graph.all_tasks() if task.metadata["kind"] == TASK_KIND_BUILD_CONTEXT)
    generate_task = next(
        task for task in graph.all_tasks() if task.metadata["kind"] == TASK_KIND_GENERATE_RESPONSE
    )

    assert generate_task.dependencies == (build_task.task_id,)


def test_return_response_task_depends_on_generate_response():
    _, graph = ExecutivePlanner().plan(_context())

    generate_task = next(
        task for task in graph.all_tasks() if task.metadata["kind"] == TASK_KIND_GENERATE_RESPONSE
    )
    return_task = next(task for task in graph.all_tasks() if task.metadata["kind"] == TASK_KIND_RETURN_RESPONSE)

    assert return_task.dependencies == (generate_task.task_id,)


def test_every_task_carries_the_contexts_execution_id():
    context = _context()

    _, graph = ExecutivePlanner().plan(context)

    assert all(task.execution_id == context.execution_id for task in graph.all_tasks())


def test_plan_is_deterministic_for_equivalent_contexts():
    # same structural inputs (conversation_id present or not) always
    # produce the same task titles/kinds/shape - no randomness, no LLM
    first_context = AgentContext(organization_id=1, conversation_id=7)
    second_context = AgentContext(organization_id=1, conversation_id=7)
    planner = ExecutivePlanner()

    _, first_graph = planner.plan(ExecutiveContext(agent_context=first_context, user_request="a"))
    _, second_graph = planner.plan(ExecutiveContext(agent_context=second_context, user_request="totally different"))

    first_kinds = [task.metadata["kind"] for task in first_graph.execution_order()]
    second_kinds = [task.metadata["kind"] for task in second_graph.execution_order()]
    assert first_kinds == second_kinds


# --- next_step / evaluate --------------------------------------------------------------


def test_next_step_returns_the_first_pending_task_in_order():
    plan = ExecutivePlanner().plan(_context())

    next_task = ExecutivePlanner().next_step(_context(), plan)

    assert next_task.title == "Retrieve memory"


def test_next_step_returns_none_once_everything_is_terminal():
    planner = ExecutivePlanner()
    decision, graph = planner.plan(_context())
    for task in graph.all_tasks():
        graph.update_task(task.with_status(TaskStatus.COMPLETED))

    assert planner.next_step(_context(), (decision, graph)) is None


def test_evaluate_is_false_until_every_task_is_terminal():
    planner = ExecutivePlanner()
    decision, graph = planner.plan(_context())

    assert planner.evaluate(_context(), (decision, graph)) is False

    for task in graph.all_tasks():
        graph.update_task(task.with_status(TaskStatus.COMPLETED))

    assert planner.evaluate(_context(), (decision, graph)) is True


def test_replan_produces_a_fresh_equivalent_plan():
    planner = ExecutivePlanner()
    context = _context()
    previous_plan = planner.plan(context)

    new_decision, new_graph = planner.replan(context, previous_plan)

    assert new_decision.requires_memory == previous_plan[0].requires_memory
    assert len(new_graph) == len(previous_plan[1])
