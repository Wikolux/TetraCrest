"""TaskGraph - represents the Executive's plan as a graph, not a flat list.

Only represents structure: parent/child relationships, a dependency graph,
and a valid linear execution_order() respecting dependencies. No
scheduling: no parallelism, no retries, no resource allocation - a future
milestone's scheduler would consume this graph, not be implemented here.
"""

from app.services.ai.agents.executive.task import Task


class CyclicDependencyError(Exception):
    """Raised when execution_order() finds a dependency cycle - a graph
    integrity error, not a scheduling concern."""


class TaskGraph:
    def __init__(self, tasks: tuple[Task, ...] = ()) -> None:
        self._tasks: dict[str, Task] = {task.task_id: task for task in tasks}

    def add_task(self, task: Task) -> None:
        self._tasks[task.task_id] = task

    def update_task(self, task: Task) -> None:
        """Replace an existing task by task_id - e.g. after
        task.with_status(...). Adds it if not already present."""
        self._tasks[task.task_id] = task

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def all_tasks(self) -> tuple[Task, ...]:
        return tuple(self._tasks.values())

    def roots(self) -> tuple[Task, ...]:
        """Tasks with no parent."""
        return tuple(task for task in self._tasks.values() if task.parent_task_id is None)

    def children_of(self, task_id: str) -> tuple[Task, ...]:
        return tuple(task for task in self._tasks.values() if task.parent_task_id == task_id)

    def parent_of(self, task_id: str) -> Task | None:
        task = self.get(task_id)
        if task is None or task.parent_task_id is None:
            return None
        return self.get(task.parent_task_id)

    def dependencies_of(self, task_id: str) -> tuple[Task, ...]:
        task = self.get(task_id)
        if task is None:
            return ()
        return tuple(self._tasks[dep_id] for dep_id in task.dependencies if dep_id in self._tasks)

    def execution_order(self) -> tuple[Task, ...]:
        """A valid linear order respecting every task's `dependencies` -
        Kahn's algorithm. Ties (tasks with no remaining dependencies at
        the same step) break by priority (higher first), then by
        insertion order - deterministic, not a scheduling policy.

        Raises CyclicDependencyError if the dependency graph has a cycle.
        """
        remaining = dict(self._tasks)
        ordered: list[Task] = []

        while remaining:
            ready = [
                task
                for task in remaining.values()
                if all(dep_id not in remaining for dep_id in task.dependencies)
            ]
            if not ready:
                raise CyclicDependencyError(
                    f"Cyclic dependency detected among tasks: {list(remaining.keys())}"
                )
            ready.sort(key=lambda task: -task.priority)
            for task in ready:
                ordered.append(task)
                del remaining[task.task_id]

        return tuple(ordered)

    def __len__(self) -> int:
        return len(self._tasks)

    def __contains__(self, task_id: str) -> bool:
        return task_id in self._tasks
