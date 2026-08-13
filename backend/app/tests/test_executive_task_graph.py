import pytest

from app.services.ai.agents.executive.task import Task, TaskStatus
from app.services.ai.agents.executive.task_graph import CyclicDependencyError, TaskGraph


def _task(title, **overrides):
    defaults = dict(title=title, execution_id="exec-1")
    defaults.update(overrides)
    return Task(**defaults)


def test_empty_graph():
    graph = TaskGraph()

    assert graph.all_tasks() == ()
    assert len(graph) == 0


def test_add_task_and_get():
    graph = TaskGraph()
    task = _task("a")

    graph.add_task(task)

    assert graph.get(task.task_id) is task
    assert task.task_id in graph
    assert len(graph) == 1


def test_constructed_with_initial_tasks():
    task = _task("a")

    graph = TaskGraph(tasks=(task,))

    assert graph.get(task.task_id) is task


def test_update_task_replaces_by_task_id():
    graph = TaskGraph()
    task = _task("a")
    graph.add_task(task)

    updated = task.with_status(TaskStatus.RUNNING)
    graph.update_task(updated)

    assert graph.get(task.task_id).status == TaskStatus.RUNNING
    assert len(graph) == 1


def test_roots_returns_tasks_with_no_parent():
    root = _task("root")
    child = _task("child", parent_task_id=root.task_id)
    graph = TaskGraph(tasks=(root, child))

    assert graph.roots() == (root,)


def test_children_of_returns_tasks_whose_parent_matches():
    root = _task("root")
    child_a = _task("child-a", parent_task_id=root.task_id)
    child_b = _task("child-b", parent_task_id=root.task_id)
    graph = TaskGraph(tasks=(root, child_a, child_b))

    assert set(graph.children_of(root.task_id)) == {child_a, child_b}


def test_parent_of_returns_none_for_a_root_task():
    root = _task("root")
    graph = TaskGraph(tasks=(root,))

    assert graph.parent_of(root.task_id) is None


def test_parent_of_returns_the_parent_task():
    root = _task("root")
    child = _task("child", parent_task_id=root.task_id)
    graph = TaskGraph(tasks=(root, child))

    assert graph.parent_of(child.task_id) == root


def test_dependencies_of_resolves_dependency_task_ids_to_tasks():
    a = _task("a")
    b = _task("b", dependencies=(a.task_id,))
    graph = TaskGraph(tasks=(a, b))

    assert graph.dependencies_of(b.task_id) == (a,)


def test_dependencies_of_ignores_unknown_dependency_ids():
    a = _task("a", dependencies=("missing-id",))
    graph = TaskGraph(tasks=(a,))

    assert graph.dependencies_of(a.task_id) == ()


# --- execution_order -----------------------------------------------------------------


def test_execution_order_respects_a_linear_chain():
    a = _task("a")
    b = _task("b", dependencies=(a.task_id,))
    c = _task("c", dependencies=(b.task_id,))
    graph = TaskGraph(tasks=(c, a, b))  # deliberately out of order

    order = graph.execution_order()

    assert [task.title for task in order] == ["a", "b", "c"]


def test_execution_order_places_independent_tasks_before_their_shared_dependent():
    a = _task("a")
    b = _task("b")
    c = _task("c", dependencies=(a.task_id, b.task_id))
    graph = TaskGraph(tasks=(c, a, b))

    order = graph.execution_order()

    assert order[-1].title == "c"
    assert {task.title for task in order[:2]} == {"a", "b"}


def test_execution_order_breaks_ties_by_priority_highest_first():
    low = _task("low", priority=0)
    high = _task("high", priority=10)
    graph = TaskGraph(tasks=(low, high))

    order = graph.execution_order()

    assert [task.title for task in order] == ["high", "low"]


def test_execution_order_raises_on_a_cycle():
    a = Task(title="a", execution_id="exec-1", task_id="a", dependencies=("b",))
    b = Task(title="b", execution_id="exec-1", task_id="b", dependencies=("a",))
    graph = TaskGraph(tasks=(a, b))

    with pytest.raises(CyclicDependencyError):
        graph.execution_order()


def test_execution_order_of_empty_graph_is_empty():
    assert TaskGraph().execution_order() == ()
