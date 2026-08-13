"""ExecutiveAgent - the AI Operating System's PID 1: the root execution
agent every request enters through and every future specialized agent
plugs into.

Provider-agnostic by construction: its only AI dependency is AIRuntime
(never a provider SDK, never HTTP). Memory retrieval goes through the
existing MemoryRetrievalPipeline exactly as designed; prompt assembly
goes through the existing PromptBuilder exactly as designed. Nothing here
re-implements retrieval, ranking, embedding, or prompt concatenation.

Response Flow (no shortcuts):
    User Request -> ExecutiveAgent -> Planner -> Decision -> Memory
    Retrieval -> Prompt Builder -> AIRuntime -> RuntimeResponse ->
    AgentExecutionResult -> Final Response
"""

from typing import Any

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentCapability
from app.services.ai.agents.execution import AgentExecutor
from app.services.ai.agents.executive.context import ExecutiveContext
from app.services.ai.agents.executive.decision import Decision
from app.services.ai.agents.executive.dispatcher import Dispatcher
from app.services.ai.agents.executive.events import ExecutiveEvent, ExecutiveEventPublisher, ExecutiveEventType
from app.services.ai.agents.executive.planner import (
    TASK_KIND_BUILD_CONTEXT,
    TASK_KIND_GENERATE_RESPONSE,
    TASK_KIND_RETRIEVE_CONVERSATIONS,
    TASK_KIND_RETRIEVE_MEMORY,
    TASK_KIND_RETURN_RESPONSE,
    ExecutivePlanner,
)
from app.services.ai.agents.executive.policies import ExecutivePolicy
from app.services.ai.agents.executive.state import ExecutiveState, ExecutiveStateMachine
from app.services.ai.agents.executive.task import Task, TaskStatus
from app.services.ai.agents.executive.task_graph import TaskGraph
from app.services.ai.agents.executive.task_result import TaskResult
from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.planner import AgentPlanner
from app.services.ai.agents.registry import AgentRegistry
from app.services.ai.agents.state import AgentStateMachine
from app.services.ai.agents.types import AgentIdentity
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeRequest, RuntimeResponse
from app.services.context.types import ContextPackage
from app.services.prompt_builder.builder import PromptBuilder
from app.services.retrieval.memory_retrieval_pipeline import MemoryRetrievalPipeline

_EXECUTIVE_AGENT_NAME = "executive"

_DEFAULT_IDENTITY = AgentIdentity(
    agent_id="executive",
    name=_EXECUTIVE_AGENT_NAME,
    display_name="Executive Agent",
    description=(
        "The AI Operating System's root execution agent (PID 1) - plans, "
        "retrieves memory, dispatches and delegates work, and synthesizes "
        "the final response for every request."
    ),
    version="1.0",
    owner="system",
    capabilities=AgentCapabilities(
        declared=frozenset(
            {
                AgentCapability.PLANNING,
                AgentCapability.MEMORY,
                AgentCapability.WORKFLOWS,
                AgentCapability.COMMUNICATION,
            }
        )
    ),
    permissions=("executive:root",),
)

_EMPTY_CONTEXT_PACKAGE = ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)


class ExecutiveAgent(BaseAgent):
    def __init__(
        self,
        identity: AgentIdentity | None = None,
        state_machine: AgentStateMachine | None = None,
        runtime: AIRuntime | None = None,
        retrieval_pipeline: MemoryRetrievalPipeline | None = None,
        prompt_builder: PromptBuilder | None = None,
        planner: ExecutivePlanner | None = None,
        dispatcher: Dispatcher | None = None,
        policy: ExecutivePolicy | None = None,
        event_publisher: ExecutiveEventPublisher | None = None,
        known_agents: dict[str, BaseAgent] | None = None,
        default_provider: ProviderName = ProviderName.UNKNOWN,
    ) -> None:
        super().__init__(identity or _DEFAULT_IDENTITY, state_machine)
        self._runtime_instance = runtime or AIRuntime()
        self.retrieval_pipeline = retrieval_pipeline or MemoryRetrievalPipeline()
        self.prompt_builder_instance = prompt_builder or PromptBuilder()
        self.policy = policy or ExecutivePolicy()
        self._planner_instance = planner or ExecutivePlanner(self.policy)
        self.dispatcher = dispatcher or Dispatcher()
        self.event_publisher = event_publisher or ExecutiveEventPublisher()
        self.known_agents = known_agents or {}
        self.default_provider = default_provider
        self.executive_state = ExecutiveStateMachine()

    # --- BaseAgent contract --------------------------------------------------------------

    def initialize(self) -> None:
        return None

    def execute(self, context: AgentContext) -> RuntimeResponse:
        if context.organization_id is None:
            raise ValueError("ExecutiveAgent.execute requires an AgentContext with organization_id set")
        user_request = context.agent_metadata.extra.get("user_request", "")
        executive_context = ExecutiveContext(agent_context=context, user_request=user_request)
        return self._run(executive_context)

    def pause(self) -> None:
        return None

    def resume(self) -> None:
        return None

    def cancel(self) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def health(self) -> bool:
        return True

    def capabilities(self) -> AgentCapabilities:
        return self.identity.capabilities

    def permissions(self) -> tuple[str, ...]:
        return self.identity.permissions

    def memory(self) -> AgentMemory | None:
        # No AgentMemory adapter is wired yet - the Executive reuses
        # MemoryRetrievalPipeline directly (a lower-level, already-complete
        # subsystem), rather than wrapping it in an AgentMemory just to
        # satisfy this accessor speculatively.
        return None

    def planner(self) -> AgentPlanner | None:
        return self._planner_instance

    def runtime(self) -> AIRuntime:
        return self._runtime_instance

    # --- Executive-specific public surface -----------------------------------------------

    def plan(self, context: ExecutiveContext) -> tuple[Decision, TaskGraph]:
        return self._planner_instance.plan(context)

    def dispatch(self, decision: Decision, task: Task) -> BaseAgent | None:
        if not self.policy.allow_delegation:
            return None
        if decision.requires_web and not self.policy.allow_web:
            return None
        if decision.requires_tools and not self.policy.allow_tools:
            return None
        return self.dispatcher.dispatch(decision, task, self.known_agents)

    def delegate(self, agent: BaseAgent, task: Task, context: ExecutiveContext) -> TaskResult:
        if context.agent_context.delegation_depth >= self.policy.maximum_depth:
            return TaskResult(task_id=task.task_id, success=False, error="Maximum delegation depth exceeded")

        agent_context = AgentContext(
            shared=context.shared.child(),
            agent_id=agent.identity.agent_id,
            parent_agent_id=self.identity.agent_id,
            delegation_depth=context.agent_context.delegation_depth + 1,
        )
        executor = AgentExecutor()
        result = executor.execute(agent, agent_context)
        return TaskResult(
            task_id=task.task_id,
            success=result.success,
            output=result.response,
            agent_execution_result=result,
            error=result.error,
        )

    def collect_results(self, task_results: list[TaskResult]) -> tuple[TaskResult, ...]:
        """Aggregate every task's result in order - no merging beyond
        that; build_response() is what synthesizes a final answer."""
        return tuple(task_results)

    def build_response(self, context: ExecutiveContext, task_results: list[TaskResult]) -> RuntimeResponse:
        failed = next((result for result in task_results if not result.success), None)
        if failed is not None:
            return RuntimeResponse(
                success=False,
                error=failed.error or "A task in the execution plan failed",
                **context.shared.identity_fields(),
            )

        generated = next(
            (result for result in task_results if isinstance(result.output, RuntimeResponse)), None
        )
        if generated is not None:
            return generated.output

        return RuntimeResponse(success=True, **context.shared.identity_fields())

    # --- internal orchestration -----------------------------------------------------------

    def _run(self, context: ExecutiveContext) -> RuntimeResponse:
        self.executive_state.transition(ExecutiveState.PLANNING)
        decision, graph = self.plan(context)
        self._emit(context, ExecutiveEventType.PLAN_CREATED, decision_id=decision.decision_id, task_count=len(graph))

        if decision.requires_memory:
            self.executive_state.transition(ExecutiveState.RETRIEVING_MEMORY)
        self.executive_state.transition(ExecutiveState.DISPATCHING)

        task_results: list[TaskResult] = []
        task_outputs: dict[str, Any] = {}
        failed = False

        for task in graph.execution_order():
            self._emit(context, ExecutiveEventType.TASK_CREATED, task_id=task.task_id, title=task.title)

            agent = self.dispatch(decision, task)
            if agent is not None:
                task = task.with_assigned_agent(agent.identity.agent_id)
                graph.update_task(task)
                self._emit(
                    context, ExecutiveEventType.TASK_ASSIGNED, task_id=task.task_id, agent_id=agent.identity.agent_id
                )
                self._emit(context, ExecutiveEventType.DELEGATION_STARTED, task_id=task.task_id)
                result = self.delegate(agent, task, context)
                self._emit(
                    context, ExecutiveEventType.DELEGATION_COMPLETED, task_id=task.task_id, success=result.success
                )
            else:
                result = self._handle_task(task, context, task_outputs)

            task_results.append(result)
            task_outputs[task.task_id] = result.output

            if result.success:
                graph.update_task(task.with_status(TaskStatus.COMPLETED))
                self._emit(context, ExecutiveEventType.TASK_COMPLETED, task_id=task.task_id)
            else:
                graph.update_task(task.with_status(TaskStatus.FAILED))
                self._emit(context, ExecutiveEventType.TASK_FAILED, task_id=task.task_id, error=result.error)
                failed = True
                break

        self.executive_state.transition(ExecutiveState.WAITING)
        self.executive_state.transition(ExecutiveState.COLLECTING)
        self.collect_results(task_results)
        self.executive_state.transition(ExecutiveState.RESPONDING)
        response = self.build_response(context, task_results)
        self._emit(context, ExecutiveEventType.RESPONSE_GENERATED, success=response.success)

        self.executive_state.transition(ExecutiveState.COMPLETED if not failed else ExecutiveState.FAILED)
        self.executive_state.transition(ExecutiveState.IDLE)
        return response

    def _handle_task(self, task: Task, context: ExecutiveContext, task_outputs: dict[str, Any]) -> TaskResult:
        kind = task.metadata.get("kind")
        try:
            if kind == TASK_KIND_RETRIEVE_MEMORY:
                output = self.retrieval_pipeline.search_memories(context.user_request, context.organization_id)
                return TaskResult(task_id=task.task_id, success=True, output=output)

            if kind == TASK_KIND_RETRIEVE_CONVERSATIONS:
                output = self.retrieval_pipeline.search_conversation_messages(
                    context.user_request, context.organization_id
                )
                return TaskResult(task_id=task.task_id, success=True, output=output)

            if kind == TASK_KIND_BUILD_CONTEXT:
                output = self._merge_context_packages(task, task_outputs)
                return TaskResult(task_id=task.task_id, success=True, output=output)

            if kind == TASK_KIND_GENERATE_RESPONSE:
                return self._handle_generate_response(task, context, task_outputs)

            if kind == TASK_KIND_RETURN_RESPONSE:
                return TaskResult(task_id=task.task_id, success=True, output=None)
        except Exception as exc:  # noqa: BLE001 - a task failure must never crash the Executive
            return TaskResult(task_id=task.task_id, success=False, error=str(exc))

        return TaskResult(task_id=task.task_id, success=False, error=f"Unknown task kind: {kind!r}")

    def _handle_generate_response(
        self, task: Task, context: ExecutiveContext, task_outputs: dict[str, Any]
    ) -> TaskResult:
        context_package = self._context_package_for(task, task_outputs)
        prompt_package = self.prompt_builder_instance.build(
            context.user_request,
            context_package,
            conversation_history=list(context.conversation_history),
        )
        runtime_request = RuntimeRequest(
            organization_id=context.organization_id,
            prompt_package=prompt_package,
            provider=self.default_provider,
            conversation_id=context.conversation_id,
            parent_shared=context.shared,
        )
        response = self._runtime_instance.execute(runtime_request)
        return TaskResult(task_id=task.task_id, success=response.success, output=response, error=response.error)

    @staticmethod
    def _merge_context_packages(task: Task, task_outputs: dict[str, Any]) -> ContextPackage:
        packages = [
            task_outputs[dep_id]
            for dep_id in task.dependencies
            if isinstance(task_outputs.get(dep_id), ContextPackage)
        ]
        if not packages:
            return _EMPTY_CONTEXT_PACKAGE
        if len(packages) == 1:
            return packages[0]
        return ContextPackage(
            sections=[section for package in packages for section in package.sections],
            estimated_tokens=sum(package.estimated_tokens for package in packages),
            item_count=sum(package.item_count for package in packages),
            truncated=any(package.truncated for package in packages),
        )

    @staticmethod
    def _context_package_for(task: Task, task_outputs: dict[str, Any]) -> ContextPackage:
        for dep_id in task.dependencies:
            output = task_outputs.get(dep_id)
            if isinstance(output, ContextPackage):
                return output
        return _EMPTY_CONTEXT_PACKAGE

    def _emit(self, context: ExecutiveContext, event_type: ExecutiveEventType, **data) -> None:
        self.event_publisher.publish(
            ExecutiveEvent(
                event_type=event_type,
                execution_id=context.execution_id,
                correlation_id=context.correlation_id,
                data=data,
            )
        )


AgentRegistry.register(_EXECUTIVE_AGENT_NAME, ExecutiveAgent, overwrite=True)
