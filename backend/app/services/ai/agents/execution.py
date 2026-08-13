"""AgentExecutor - owns one supervised execution cycle for a BaseAgent.

Responsibilities: validate permissions, transition state, invoke the
agent's planner, invoke the agent's own execute() (which is expected to
go through self.runtime() internally - AgentExecutor itself never touches
a provider or the runtime directly), emit lifecycle events, and return an
AgentExecutionResult. A failure inside agent.execute() is caught and
reported via the result (state=FAILED, error set) rather than raised -
permission failures are the one exception, raised immediately as a
caller/configuration error, mirroring how KernelRuntime raises for
structural pre-checks while never raising for execution failures.
"""

import time
from datetime import UTC, datetime

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentEventType, AgentState
from app.services.ai.agents.events import AgentEvent, AgentEventPublisher
from app.services.ai.agents.policies import PermissionPolicy
from app.services.ai.agents.types import AgentExecutionResult, AgentPermissionError
from app.services.ai.kernel.metrics import ExecutionMetrics, TokenUsageReference
from app.services.ai.runtime.types import RuntimeResponse

_MS_PER_SECOND = 1000


class AgentExecutor:
    def __init__(
        self,
        event_publisher: AgentEventPublisher | None = None,
        permission_policy: PermissionPolicy | None = None,
    ) -> None:
        self.event_publisher = event_publisher or AgentEventPublisher()
        self.permission_policy = permission_policy

    def execute(self, agent: BaseAgent, context: AgentContext) -> AgentExecutionResult:
        self._validate_permissions(agent)

        started_at = datetime.now(UTC)
        start = time.monotonic()
        events: list[AgentEvent] = []

        agent.state_machine.transition(AgentState.RUNNING)
        self._emit(events, agent, AgentEventType.STARTED, context)

        planner = agent.planner()
        if planner is not None:
            planner.plan(context)

        try:
            response = agent.execute(context)
        except Exception as exc:  # noqa: BLE001 - an agent's own failure must never crash the executor
            agent.state_machine.transition(AgentState.FAILED)
            self._emit(events, agent, AgentEventType.FAILED, context, error=str(exc))
            return self._build_result(agent, context, started_at, start, events, response=None, error=str(exc))

        agent.state_machine.transition(AgentState.READY)
        self._emit(events, agent, AgentEventType.COMPLETED, context)
        return self._build_result(agent, context, started_at, start, events, response=response, error=None)

    def _validate_permissions(self, agent: BaseAgent) -> None:
        policy = self.permission_policy
        if policy is None:
            return
        if policy.deny_all:
            raise AgentPermissionError(f"Agent '{agent.identity.agent_id}' is denied by policy")
        if policy.allow_all:
            return
        granted = set(agent.permissions())
        missing = [permission for permission in policy.required_permissions if permission not in granted]
        if missing:
            raise AgentPermissionError(
                f"Agent '{agent.identity.agent_id}' is missing required permissions: {missing}"
            )

    def _emit(
        self,
        events: list[AgentEvent],
        agent: BaseAgent,
        event_type: AgentEventType,
        context: AgentContext,
        **data,
    ) -> None:
        event = AgentEvent(
            event_type=event_type,
            agent_id=agent.identity.agent_id,
            execution_id=context.execution_id,
            data=data,
        )
        events.append(event)
        self.event_publisher.publish(event)

    @staticmethod
    def _build_result(
        agent: BaseAgent,
        context: AgentContext,
        started_at: datetime,
        start: float,
        events: list[AgentEvent],
        response: RuntimeResponse | None,
        error: str | None,
    ) -> AgentExecutionResult:
        duration_ms = (time.monotonic() - start) * _MS_PER_SECOND
        token_usage = None
        if response is not None and response.usage is not None:
            token_usage = TokenUsageReference(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
        metrics = ExecutionMetrics(
            duration_ms=duration_ms,
            latency_ms=response.latency_ms if response is not None else None,
            token_usage=token_usage,
            execution_id=context.execution_id,
        )
        return AgentExecutionResult(
            agent_id=agent.identity.agent_id,
            state=agent.state_machine.state,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            duration_ms=duration_ms,
            response=response,
            events=tuple(events),
            metrics=metrics,
            error=error,
            **context.shared.identity_fields(),
        )
