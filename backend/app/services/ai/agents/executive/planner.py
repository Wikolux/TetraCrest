"""ExecutivePlanner - a deterministic, rule-based planner. No LLM
reasoning, no chain-of-thought: given a request, it produces a fixed,
predictable sequence of Tasks based only on simple, objective facts about
the request (does it reference a conversation, does policy allow memory)
- never by analyzing the meaning of the request text itself.

Implements AgentPlanner (app.services.ai.agents.planner) - reusing the
existing abstraction rather than inventing a parallel one, per this
milestone's "reuse existing abstractions" requirement. AgentPlanner's
plan()/replan()/evaluate()/next_step() signatures are typed against
AgentContext/Any; this planner narrows the parameter it actually expects
to ExecutiveContext (a superset of what an AgentContext carries) and
returns (Decision, TaskGraph) tuples where AgentPlanner's contract says
Any - Python's ABC mechanism only requires the methods exist, not that
their signatures widen/narrow in any particular way.

Task titles/ordering below are a literal, generic version of this
milestone's own example ("Help me prepare for an Anthropic interview" ->
retrieve memory, retrieve conversations, build context, generate
response, return response) - deliberately not interview-specific, since a
deterministic planner must behave identically regardless of what the
request is actually about.
"""

from app.services.ai.agents.enums import AgentCapability
from app.services.ai.agents.executive.context import ExecutiveContext
from app.services.ai.agents.executive.decision import Decision
from app.services.ai.agents.executive.policies import ExecutivePolicy
from app.services.ai.agents.executive.task import Task, TaskStatus
from app.services.ai.agents.executive.task_graph import TaskGraph
from app.services.ai.agents.planner import AgentPlanner

TASK_KIND_RETRIEVE_MEMORY = "retrieve_memory"
TASK_KIND_RETRIEVE_CONVERSATIONS = "retrieve_conversations"
TASK_KIND_BUILD_CONTEXT = "build_context"
TASK_KIND_GENERATE_RESPONSE = "generate_response"
TASK_KIND_RETURN_RESPONSE = "return_response"


class ExecutivePlanner(AgentPlanner):
    def __init__(self, policy: ExecutivePolicy | None = None) -> None:
        self.policy = policy or ExecutivePolicy()

    def plan(self, context: ExecutiveContext) -> tuple[Decision, TaskGraph]:
        decision = self._decide(context)
        graph = self._build_graph(context, decision)
        return decision, graph

    def replan(
        self, context: ExecutiveContext, previous_plan: tuple[Decision, TaskGraph]
    ) -> tuple[Decision, TaskGraph]:
        """No adaptive replanning logic exists yet (no LLM reasoning to
        drive it) - replanning simply produces a fresh deterministic plan
        from the current context."""
        return self.plan(context)

    def evaluate(self, context: ExecutiveContext, plan: tuple[Decision, TaskGraph]) -> bool:
        """Whether every task in the plan reached a terminal state."""
        _, graph = plan
        terminal = (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED)
        tasks = graph.all_tasks()
        return bool(tasks) and all(task.status in terminal for task in tasks)

    def next_step(self, context: ExecutiveContext, plan: tuple[Decision, TaskGraph]) -> Task | None:
        """The first still-pending task in dependency order, or None if
        nothing is left to run."""
        _, graph = plan
        for task in graph.execution_order():
            if task.status == TaskStatus.PENDING:
                return task
        return None

    def _decide(self, context: ExecutiveContext) -> Decision:
        has_conversation = context.conversation_id is not None
        return Decision(
            reason="Deterministic default plan: retrieve context, build a prompt, execute via the runtime.",
            confidence=1.0,
            requires_memory=True,
            requires_runtime=True,
            requires_delegation=False,
            requires_tools=False,
            requires_web=False,
            selected_agent=None,
            priority=0,
            metadata={"has_conversation_history": has_conversation},
        )

    def _build_graph(self, context: ExecutiveContext, decision: Decision) -> TaskGraph:
        execution_id = context.execution_id
        graph = TaskGraph()

        def _task(
            title: str,
            kind: str,
            dependencies: tuple[str, ...] = (),
            required_capability: AgentCapability | None = None,
        ) -> Task:
            metadata: dict[str, object] = {"kind": kind}
            if required_capability is not None:
                metadata["required_capability"] = required_capability
            task = Task(
                title=title,
                execution_id=execution_id,
                dependencies=dependencies,
                metadata=metadata,
            )
            graph.add_task(task)
            return task

        retrieval_task_ids: list[str] = []

        if decision.requires_memory:
            memory_task = _task(
                "Retrieve memory", TASK_KIND_RETRIEVE_MEMORY, required_capability=AgentCapability.MEMORY
            )
            retrieval_task_ids.append(memory_task.task_id)

        if context.conversation_id is not None:
            conversation_task = _task(
                "Retrieve previous conversations",
                TASK_KIND_RETRIEVE_CONVERSATIONS,
                required_capability=AgentCapability.MEMORY,
            )
            retrieval_task_ids.append(conversation_task.task_id)

        build_context_task = _task(
            "Build prompt context", TASK_KIND_BUILD_CONTEXT, dependencies=tuple(retrieval_task_ids)
        )
        generate_task = _task(
            "Generate response", TASK_KIND_GENERATE_RESPONSE, dependencies=(build_context_task.task_id,)
        )
        _task("Return response", TASK_KIND_RETURN_RESPONSE, dependencies=(generate_task.task_id,))

        return graph
