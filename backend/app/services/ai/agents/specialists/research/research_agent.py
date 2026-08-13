"""ResearchAgent - the first production specialist: research, information
gathering, knowledge synthesis, report generation, comparative analysis,
and executive summaries. No internet/browser/HTTP implementation - only
orchestration over the existing Memory, Tool, and Runtime subsystems via
their adapters.

Research Execution Flow (no shortcuts):
    SpecialistRequest -> memory retrieval (AgentMemory, backed by
    MemoryAdapter) -> prompt build (PromptBuilder) -> required-tools
    determination -> Tool Framework (ToolAdapter) -> ToolResults ->
    synthesis (ResearchSynthesizer) -> RuntimeRequest ->
    AIRuntime.execute() (RuntimeAdapter) -> ResearchReport ->
    SpecialistResponse
"""

from typing import Any

from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentCapability
from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.planner import AgentPlanner
from app.services.ai.agents.registry import AgentRegistry
from app.services.ai.agents.specialists.coordinator import SpecialistCoordinator
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
from app.services.ai.agents.specialists.registry import SpecialistRegistry
from app.services.ai.agents.specialists.research.context import build_research_context
from app.services.ai.agents.specialists.research.events import (
    ResearchEvent,
    ResearchEventPublisher,
    ResearchEventType,
)
from app.services.ai.agents.specialists.research.planner import ResearchPlanner
from app.services.ai.agents.specialists.research.policies import ResearchPolicy
from app.services.ai.agents.specialists.research.report import ResearchReport
from app.services.ai.agents.specialists.research.state import ResearchState, ResearchStateMachine
from app.services.ai.agents.specialists.research.synthesizer import ResearchSynthesizer, SynthesisResult
from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.metrics import aggregate_metrics
from app.services.ai.agents.specialists.shared.policies import SpecialistExecutionPolicy
from app.services.ai.agents.specialists.shared.request import SpecialistRequest
from app.services.ai.agents.specialists.shared.response import SpecialistResponse
from app.services.ai.agents.specialists.shared.task import SpecialistTask, SpecialistTaskType
from app.services.ai.agents.specialists.specialist_agent import SpecialistAgent
from app.services.ai.agents.specialists.tool_adapter import ToolAdapter
from app.services.ai.agents.state import AgentStateMachine
from app.services.ai.agents.types import AgentIdentity
from app.services.ai.kernel.metrics import ExecutionMetrics
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.cancellation import CancellationToken
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeRequest, RuntimeResponse
from app.services.ai.tools.discovery import ToolDiscovery
from app.services.ai.tools.enums import ToolCategory
from app.services.ai.tools.execution import ToolExecutor
from app.services.ai.tools.manager import ToolManager
from app.services.ai.tools.policies import ToolExecutionPolicy
from app.services.ai.tools.result import ToolResult
from app.services.context.types import ContextPackage
from app.services.prompt_builder.builder import PromptBuilder

_RESEARCH_AGENT_NAME = "research"

_SUPPORTED_TASKS: frozenset[SpecialistTaskType] = frozenset(
    {
        SpecialistTaskType.RESEARCH,
        SpecialistTaskType.ANALYSIS,
        SpecialistTaskType.SUMMARIZATION,
        SpecialistTaskType.COMPARISON,
        SpecialistTaskType.VERIFICATION,
        SpecialistTaskType.INVESTIGATION,
    }
)

_DEFAULT_IDENTITY = AgentIdentity(
    agent_id="research",
    name=_RESEARCH_AGENT_NAME,
    display_name="Research Agent",
    description=(
        "Specialist agent responsible for research, information gathering, "
        "knowledge synthesis, report generation, comparative analysis, and "
        "executive summaries."
    ),
    version="1.0",
    owner="system",
    capabilities=AgentCapabilities(
        declared=frozenset({AgentCapability.RESEARCH, AgentCapability.MEMORY, AgentCapability.REASONING})
    ),
    permissions=("specialist:research",),
)

_EMPTY_CONTEXT_PACKAGE = ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)


class ResearchAgent(SpecialistAgent):
    def __init__(
        self,
        identity: AgentIdentity | None = None,
        state_machine: AgentStateMachine | None = None,
        runtime_adapter: RuntimeAdapter | None = None,
        memory_adapter: AgentMemory | None = None,
        tool_adapter: ToolAdapter | None = None,
        planner: ResearchPlanner | None = None,
        synthesizer: ResearchSynthesizer | None = None,
        policy: SpecialistExecutionPolicy | None = None,
        research_policy: ResearchPolicy | None = None,
        event_publisher: ResearchEventPublisher | None = None,
        default_provider: ProviderName = ProviderName.UNKNOWN,
    ) -> None:
        super().__init__(identity or _DEFAULT_IDENTITY, state_machine)
        self.policy = policy or SpecialistExecutionPolicy()
        self.research_policy = research_policy or ResearchPolicy()
        self.coordinator = SpecialistCoordinator(
            planner=planner or ResearchPlanner(),
            memory_adapter=memory_adapter or MemoryAdapter(),
            tool_adapter=tool_adapter or self._default_tool_adapter(),
            runtime_adapter=runtime_adapter or RuntimeAdapter(),
            synthesizer=synthesizer or ResearchSynthesizer(),
        )
        self.event_publisher = event_publisher or ResearchEventPublisher()
        self.default_provider = default_provider
        self.research_state = ResearchStateMachine()

    def _default_tool_adapter(self) -> ToolAdapter:
        """Build a ToolAdapter whose underlying ToolExecutor is actually
        configured from self.policy (maximum_depth/timeout_seconds/
        retry_policy) - without this, self.policy.retry_policy would be a
        declared field with no effect on tool execution at all, exactly
        the kind of gap this milestone asks to be fixed rather than
        deferred. Only used when the caller doesn't inject their own
        tool_adapter - an explicit injection is never overridden."""
        return ToolAdapter(
            manager=ToolManager(
                executor=ToolExecutor(
                    execution_policy=ToolExecutionPolicy(
                        maximum_depth=self.policy.maximum_depth,
                        timeout_seconds=self.policy.timeout_seconds,
                        retry_policy=self.policy.retry_policy,
                    )
                )
            )
        )

    # --- BaseAgent contract --------------------------------------------------------------

    def initialize(self) -> None:
        return None

    def execute(self, context: AgentContext) -> RuntimeResponse:
        if context.organization_id is None:
            raise ValueError("ResearchAgent.execute requires an AgentContext with organization_id set")
        request = self._extract_request(context)
        specialist_context = build_research_context(context, request)
        response = self.research(request, specialist_context)
        return RuntimeResponse(success=response.success, error=response.error, **context.shared.identity_fields())

    def pause(self) -> None:
        return None

    def resume(self) -> None:
        return None

    def cancel(self) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def health(self) -> bool:
        return self.health_check()

    def capabilities(self) -> AgentCapabilities:
        return self.identity.capabilities

    def permissions(self) -> tuple[str, ...]:
        return self.identity.permissions

    def memory(self) -> AgentMemory | None:
        # MemoryAdapter implements AgentMemory as of M20.6 - this is the
        # same instance _retrieve_memory() uses internally, exposed
        # through the BaseAgent contract rather than kept private.
        return self.coordinator.memory_adapter

    def planner(self) -> AgentPlanner:
        return self.coordinator.planner

    def runtime(self) -> AIRuntime:
        return self.coordinator.runtime_adapter.runtime

    # --- SpecialistAgent contract ----------------------------------------------------------

    def specialization(self) -> str:
        return "research"

    def supported_tasks(self) -> frozenset[SpecialistTaskType]:
        return _SUPPORTED_TASKS

    def plan(self, context: SpecialistContext) -> tuple[SpecialistTask, ...]:
        return self.coordinator.planner.plan(context)

    def evaluate(self, response: SpecialistResponse) -> bool:
        return response.success and response.confidence >= self.research_policy.minimum_confidence

    def self_check(self) -> bool:
        """Internal wiring consistency - no I/O."""
        return all(
            collaborator is not None
            for collaborator in (
                self.coordinator.planner,
                self.coordinator.memory_adapter,
                self.coordinator.tool_adapter,
                self.coordinator.runtime_adapter,
                self.coordinator.synthesizer,
            )
        )

    def health_check(self) -> bool:
        """External dependency health. No concrete tool/provider is
        registered anywhere yet in this milestone, so there is nothing
        meaningful to probe without side effects - this honestly reduces
        to self_check() today, and is the seam a future milestone would
        extend to actually probe memory/tool/runtime reachability."""
        return self.self_check()

    # --- the rich, research-specific entry point --------------------------------------------

    def research(
        self,
        request: SpecialistRequest,
        context: SpecialistContext,
        cancellation_token: CancellationToken | None = None,
    ) -> SpecialistResponse:
        if context.agent_context.delegation_depth >= self.policy.maximum_depth:
            return SpecialistResponse(
                success=False, error="Maximum execution depth exceeded", **context.shared.identity_fields()
            )

        self.research_state.transition(ResearchState.PLANNING)
        self._emit(context, ResearchEventType.RESEARCH_STARTED)

        try:
            tasks = self.plan(context)
            self._emit(context, ResearchEventType.PLAN_CREATED, task_count=len(tasks))

            self.research_state.transition(ResearchState.RETRIEVING)
            memory_package = self._retrieve_memory(request, context)
            self._emit(context, ResearchEventType.MEMORY_RETRIEVED)

            self.research_state.transition(ResearchState.ANALYZING)
            tool_results = self._invoke_tools(request, context, cancellation_token)
            self._emit(context, ResearchEventType.TOOLS_COMPLETED, tool_count=len(tool_results))

            self.research_state.transition(ResearchState.SYNTHESIZING)
            synthesis = self.coordinator.synthesizer.synthesize(memory_package, tool_results, None)
            self._emit(context, ResearchEventType.SYNTHESIS_COMPLETED)

            self.research_state.transition(ResearchState.GENERATING)
            runtime_response = self._generate(request, context, memory_package)

            report = self._build_report(request, synthesis, runtime_response)
            self._emit(context, ResearchEventType.REPORT_GENERATED)

            response = self._build_response(context, report, runtime_response, tool_results)
        except Exception as exc:  # noqa: BLE001 - a research failure must never crash the caller
            response = SpecialistResponse(success=False, error=str(exc), **context.shared.identity_fields())

        if response.success:
            self.research_state.transition(ResearchState.COMPLETED)
            self._emit(context, ResearchEventType.RESEARCH_COMPLETED)
        else:
            self.research_state.transition(ResearchState.FAILED)
            self._emit(context, ResearchEventType.RESEARCH_FAILED)
        self.research_state.transition(ResearchState.IDLE)

        return response

    # --- internal helpers ------------------------------------------------------------------

    @staticmethod
    def _extract_request(context: AgentContext) -> SpecialistRequest:
        raw = context.agent_metadata.extra.get("specialist_request")
        if isinstance(raw, SpecialistRequest):
            return raw
        objective = context.agent_metadata.extra.get("objective", "")
        return SpecialistRequest(objective=objective)

    def _required_tools(self, request: SpecialistRequest) -> tuple[str, ...]:
        if not request.tools_allowed or not request.web_allowed:
            return ()
        return ToolDiscovery().by_category(ToolCategory.SEARCH)

    def _retrieve_memory(self, request: SpecialistRequest, context: SpecialistContext) -> ContextPackage | None:
        # Goes through AgentMemory.retrieve() (scope="all" by default,
        # matching the previous direct retrieve_all() call exactly) rather
        # than MemoryAdapter.retrieve_all() directly - ResearchAgent
        # depends on the abstract memory contract here, not the concrete
        # adapter, per M20.6.
        if not request.memory_allowed:
            return None
        return self.coordinator.memory_adapter.retrieve(request.objective, organization_id=context.organization_id)

    def _invoke_tools(
        self,
        request: SpecialistRequest,
        context: SpecialistContext,
        cancellation_token: CancellationToken | None = None,
    ) -> tuple[ToolResult, ...]:
        tool_ids = self._required_tools(request)
        if not tool_ids:
            return ()
        results = [
            self.coordinator.tool_adapter.invoke(
                tool_id,
                {"query": request.objective},
                shared=context.shared,
                agent_id=self.identity.agent_id,
                cancellation_token=cancellation_token,
            )
            for tool_id in tool_ids
        ]
        return tuple(results)

    def _generate(
        self, request: SpecialistRequest, context: SpecialistContext, memory_package: ContextPackage | None
    ) -> RuntimeResponse:
        context_package = memory_package if memory_package is not None else _EMPTY_CONTEXT_PACKAGE
        prompt_package = PromptBuilder().build(request.objective, context_package)
        runtime_request = RuntimeRequest(
            organization_id=context.organization_id,
            prompt_package=prompt_package,
            provider=self.default_provider,
            conversation_id=context.conversation_id,
            parent_shared=context.shared,
        )
        return self.coordinator.runtime_adapter.execute(runtime_request)

    @staticmethod
    def _build_report(
        request: SpecialistRequest, synthesis: SynthesisResult, runtime_response: RuntimeResponse
    ) -> ResearchReport:
        runtime_text = (
            runtime_response.conversation_response.text if runtime_response.conversation_response else ""
        )
        return ResearchReport(
            executive_summary=runtime_text or request.objective,
            detailed_findings=synthesis.key_points,
            evidence=synthesis.sources,
            confidence=1.0 if runtime_response.success else 0.0,
            knowledge_gaps=synthesis.knowledge_gaps,
            recommended_next_actions=(),
            references=synthesis.sources,
            appendices=(),
            metadata={"objective": request.objective},
        )

    @staticmethod
    def _build_response(
        context: SpecialistContext,
        report: ResearchReport,
        runtime_response: RuntimeResponse,
        tool_results: tuple[ToolResult, ...],
    ) -> SpecialistResponse:
        tool_metrics = tuple(result.metrics for result in tool_results if result.metrics is not None)
        runtime_metrics = ExecutionMetrics(latency_ms=runtime_response.latency_ms, execution_id=context.execution_id)
        metrics = aggregate_metrics(*tool_metrics, runtime_metrics, execution_id=context.execution_id)

        return SpecialistResponse(
            success=runtime_response.success,
            summary=report.executive_summary,
            findings=report.detailed_findings,
            confidence=report.confidence,
            sources=report.references,
            recommendations=report.recommended_next_actions,
            artifacts=report.appendices,
            reasoning_summary="; ".join(report.detailed_findings[:3]),
            execution_metrics=metrics,
            error=runtime_response.error,
            **context.shared.identity_fields(),
        )

    def _emit(self, context: SpecialistContext, event_type: ResearchEventType, **data: Any) -> None:
        self.event_publisher.publish(
            ResearchEvent(
                event_type=event_type,
                execution_id=context.execution_id,
                correlation_id=context.correlation_id,
                agent_id=self.identity.agent_id,
                data=data,
            )
        )


AgentRegistry.register(_RESEARCH_AGENT_NAME, ResearchAgent, overwrite=True)
SpecialistRegistry.register(
    _RESEARCH_AGENT_NAME,
    ResearchAgent,
    specialization="research",
    supported_tasks=_SUPPORTED_TASKS,
    overwrite=True,
)
