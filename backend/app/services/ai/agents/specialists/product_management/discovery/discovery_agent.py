"""DiscoverySpecialist (CP-02, Milestone 3) - the first Product Management
Intelligence Pack specialist: validates whether a candidate product
problem is real and worth solving, before engineering effort is committed
(PRD §15, Architecture §3/§16/§17).

Built with zero new platform mechanism, mirroring ResearchAgent/
PersonalIntelligenceAgent exactly:

- Memory: every read/write goes through ProfessionalMemoryService (which
  itself never bypasses AgentMemory) - never a second memory path.
- Runtime generation: every synthesis goes through AIRuntime via
  RuntimeAdapter, prompts assembled by PromptBuilder - identical to every
  existing specialist.
- Research: never performed here. `AgentCapability.RESEARCH` is never
  declared, and ResearchAgent is never imported. FRAME_RESEARCH_QUESTION
  only frames a well-scoped question and emits a distinguishing event
  (Architecture §15 point 4); the Executive is what dispatches that
  question to ResearchAgent, via the existing capability-matched
  Dispatcher, in a later, separate delegation (Architecture §9 shape 1,
  Implementation_Plan.md §10). RECORD_RESEARCH_FINDING records what comes
  back from that separate turn - CP-02 never guesses at findings.
- Evidence discipline: DiscoveryRecommendation (outputs.py) cannot be
  constructed without either citing evidence_ids or stating an explicit
  evidence_gap - "no fabricated conclusions" is a property of the type,
  not a hope about the prompt (ARR §7/§8).

This agent deliberately does NOT declare AgentCapability.MEMORY, for the
identical collision-avoidance reason PersonalIntelligenceAgent/ResearchAgent
never declare it beyond their own genuine needs: ExecutivePlanner's
built-in retrieve_memory/retrieve_conversations tasks are tagged
required_capability=AgentCapability.MEMORY, and a DiscoverySpecialist
declaring MEMORY could have those internal steps mis-routed to it instead
of being handled by ExecutiveAgent._handle_task() (Architecture §19).
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
from app.services.ai.agents.specialists.product_management.discovery.context import build_discovery_context
from app.services.ai.agents.specialists.product_management.discovery.events import (
    DiscoveryEvent,
    DiscoveryEventPublisher,
    DiscoveryEventType,
)
from app.services.ai.agents.specialists.product_management.discovery.outputs import (
    DiscoveryRecommendation,
    DiscoveryReport,
    DiscoverySummary,
    HypothesisItem,
    InterviewInsights,
    InterviewSummary,
    JTBDAnalysis,
    OpportunityItem,
    OpportunityList,
    PersonaSummary,
    ProblemStatement,
)
from app.services.ai.agents.specialists.product_management.discovery.planner import DiscoveryPlanner
from app.services.ai.agents.specialists.product_management.discovery.policies import DiscoveryPolicy
from app.services.ai.agents.specialists.product_management.discovery.request import DiscoveryOperation, DiscoveryRequest
from app.services.ai.agents.specialists.product_management.discovery.state import DiscoveryState, DiscoveryStateMachine
from app.services.ai.agents.specialists.product_management.memory_service import ProfessionalMemoryService
from app.services.ai.agents.specialists.product_management.shared.discovery_finding import DiscoveryFinding, HypothesisStatus
from app.services.ai.agents.specialists.product_management.shared.research_finding import ResearchFinding
from app.services.ai.agents.specialists.product_management.shared.types import (
    MEMORY_TYPE_DISCOVERY_FINDING,
    MEMORY_TYPE_RESEARCH_FINDING,
)
from app.services.ai.agents.specialists.registry import SpecialistRegistry
from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.policies import SpecialistExecutionPolicy
from app.services.ai.agents.specialists.shared.request import SpecialistRequest
from app.services.ai.agents.specialists.shared.response import SpecialistResponse
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType
from app.services.ai.agents.specialists.specialist_agent import SpecialistAgent
from app.services.ai.agents.specialists.tool_adapter import ToolAdapter
from app.services.ai.agents.state import AgentStateMachine
from app.services.ai.agents.types import AgentIdentity
from app.services.ai.kernel.metrics import ExecutionMetrics
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.cancellation import CancellationToken
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeRequest, RuntimeResponse
from app.services.ai.tools.execution import ToolExecutor
from app.services.ai.tools.manager import ToolManager
from app.services.ai.tools.policies import ToolExecutionPolicy
from app.services.context.types import ContextItem, ContextPackage, ContextSection
from app.services.prompt_builder.builder import PromptBuilder

_DISCOVERY_AGENT_NAME = "discovery"

_SUPPORTED_TASKS: frozenset[SpecialistTaskType] = frozenset({SpecialistTaskType.INVESTIGATION})

_DEFAULT_IDENTITY = AgentIdentity(
    agent_id="discovery",
    name=_DISCOVERY_AGENT_NAME,
    display_name="Discovery Specialist",
    description=(
        "CP-02: validates whether a candidate product problem is real and worth solving - problem "
        "validation, Jobs-to-be-Done framing, customer-interview synthesis, opportunity assessment, "
        "and hypothesis tracking - through the existing Memory Framework, Prompt Builder, and Runtime, "
        "delegating genuine research questions to the existing ResearchAgent via the Executive rather "
        "than reimplementing research."
    ),
    version="1.0",
    owner="system",
    capabilities=AgentCapabilities(declared=frozenset({AgentCapability.REASONING, AgentCapability.PLANNING})),
    permissions=("specialist:discovery",),
)

_EMPTY_CONTEXT_PACKAGE = ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)


class DiscoverySpecialist(SpecialistAgent):
    def __init__(
        self,
        identity: AgentIdentity | None = None,
        state_machine: AgentStateMachine | None = None,
        runtime_adapter: RuntimeAdapter | None = None,
        memory_adapter: AgentMemory | None = None,
        tool_adapter: ToolAdapter | None = None,
        planner: DiscoveryPlanner | None = None,
        synthesizer: Any = None,
        policy: SpecialistExecutionPolicy | None = None,
        discovery_policy: DiscoveryPolicy | None = None,
        event_publisher: DiscoveryEventPublisher | None = None,
        memory_service: ProfessionalMemoryService | None = None,
        default_provider: ProviderName = ProviderName.UNKNOWN,
    ) -> None:
        super().__init__(identity or _DEFAULT_IDENTITY, state_machine)
        self.policy = policy or SpecialistExecutionPolicy()
        self.discovery_policy = discovery_policy or DiscoveryPolicy()
        resolved_memory = memory_adapter or MemoryAdapter()
        self.memory_service = memory_service or ProfessionalMemoryService(resolved_memory)
        self.coordinator = SpecialistCoordinator(
            planner=planner or DiscoveryPlanner(),
            memory_adapter=resolved_memory,
            tool_adapter=tool_adapter or self._default_tool_adapter(),
            runtime_adapter=runtime_adapter or RuntimeAdapter(),
            synthesizer=synthesizer,
        )
        self.event_publisher = event_publisher or DiscoveryEventPublisher()
        self.default_provider = default_provider
        self.discovery_state = DiscoveryStateMachine()
        self._handlers = {
            DiscoveryOperation.VALIDATE_PROBLEM: self._handle_validate_problem,
            DiscoveryOperation.FRAME_JTBD: self._handle_frame_jtbd,
            DiscoveryOperation.SYNTHESIZE_INTERVIEW: self._handle_synthesize_interview,
            DiscoveryOperation.ASSESS_OPPORTUNITY: self._handle_assess_opportunity,
            DiscoveryOperation.FRAME_PERSONA: self._handle_frame_persona,
            DiscoveryOperation.TRACK_HYPOTHESIS: self._handle_track_hypothesis,
            DiscoveryOperation.GENERATE_RECOMMENDATION: self._handle_generate_recommendation,
            DiscoveryOperation.RUN_DISCOVERY_SESSION: self._handle_run_discovery_session,
            DiscoveryOperation.SUMMARIZE: self._handle_summarize,
            DiscoveryOperation.FRAME_RESEARCH_QUESTION: self._handle_frame_research_question,
            DiscoveryOperation.RECORD_RESEARCH_FINDING: self._handle_record_research_finding,
            DiscoveryOperation.RECALL: self._handle_recall,
        }

    def _default_tool_adapter(self) -> ToolAdapter:
        """Mirrors ResearchAgent/PersonalIntelligenceAgent's own
        _default_tool_adapter() exactly - a ToolAdapter whose underlying
        ToolExecutor is actually configured from self.policy. No v1/v2
        Discovery journey exercises a concrete tool (Implementation_Plan.md
        §12); this keeps the integration point wired and consistent with
        every other specialist regardless."""
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
            raise ValueError("DiscoverySpecialist.execute requires an AgentContext with organization_id set")
        request = self._extract_request(context)
        specialist_request = SpecialistRequest(objective=request.text or request.title)
        specialist_context = build_discovery_context(context, specialist_request)
        response = self.process(request, specialist_context)
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
        return self.coordinator.memory_adapter

    def planner(self) -> AgentPlanner:
        return self.coordinator.planner

    def runtime(self) -> AIRuntime:
        return self.coordinator.runtime_adapter.runtime

    # --- SpecialistAgent contract ----------------------------------------------------------

    def specialization(self) -> str:
        return "discovery"

    def supported_tasks(self) -> frozenset[SpecialistTaskType]:
        return _SUPPORTED_TASKS

    def plan(self, context: SpecialistContext) -> tuple:
        return self.coordinator.planner.plan(context)

    def evaluate(self, response: SpecialistResponse) -> bool:
        return response.success and response.confidence >= self.discovery_policy.minimum_confidence

    def self_check(self) -> bool:
        return all(
            collaborator is not None
            for collaborator in (
                self.coordinator.planner,
                self.coordinator.memory_adapter,
                self.coordinator.tool_adapter,
                self.coordinator.runtime_adapter,
                self.memory_service,
            )
        )

    def health_check(self) -> bool:
        return self.self_check()

    # --- the rich, Discovery-specific entry point --------------------------------------------

    def process(
        self,
        request: DiscoveryRequest,
        context: SpecialistContext,
        cancellation_token: CancellationToken | None = None,
    ) -> SpecialistResponse:
        if context.agent_context.delegation_depth >= self.policy.maximum_depth:
            return SpecialistResponse(
                success=False, error="Maximum execution depth exceeded", **context.shared.identity_fields()
            )

        self.discovery_state.transition(DiscoveryState.INTERPRETING)
        self._emit(context, DiscoveryEventType.REQUEST_STARTED)

        handler = self._handlers.get(request.operation)
        try:
            if handler is None:
                raise ValueError(f"Unsupported operation: {request.operation!r}")
            response = handler(request, context)
        except Exception as exc:  # noqa: BLE001 - a request failure must never crash the caller
            if self.discovery_state.can_transition(DiscoveryState.FAILED):
                self.discovery_state.transition(DiscoveryState.FAILED)
            response = SpecialistResponse(success=False, error=str(exc), **context.shared.identity_fields())

        if response.success:
            self.discovery_state.transition(DiscoveryState.COMPLETED)
            self._emit(context, DiscoveryEventType.REQUEST_COMPLETED)
        else:
            if self.discovery_state.state != DiscoveryState.FAILED:
                self.discovery_state.transition(DiscoveryState.FAILED)
            self._emit(context, DiscoveryEventType.REQUEST_FAILED, error=response.error)
        self.discovery_state.transition(DiscoveryState.IDLE)

        return response

    # --- operation handlers -----------------------------------------------------------------
    # Every handler leaves discovery_state in SYNTHESIZING when it returns -
    # process() owns the terminal COMPLETED/FAILED transition uniformly.

    def _handle_validate_problem(self, request: DiscoveryRequest, context: SpecialistContext) -> SpecialistResponse:
        package = self._gather(request.text, context)
        self.discovery_state.transition(DiscoveryState.STRUCTURING)
        statement = ProblemStatement(
            statement=request.text, target_segment=request.segment, evidence_ids=self._evidence_ids(package)
        )
        finding = self._record_finding(
            summary=statement.statement, source=request.source, hypothesis=request.hypothesis, context=context
        )
        self._emit(context, DiscoveryEventType.PROBLEM_STATEMENT_DRAFTED)
        runtime_response = self._synthesize(
            f"Frame this problem clearly, distinguishing assumption from validated fact: {statement.statement}",
            package,
            context,
        )
        return self._response_from_runtime(
            context, runtime_response, findings=(finding.to_memory_content(),), sources=statement.evidence_ids
        )

    def _handle_frame_jtbd(self, request: DiscoveryRequest, context: SpecialistContext) -> SpecialistResponse:
        package = self._gather(request.text, context)
        self.discovery_state.transition(DiscoveryState.STRUCTURING)
        analysis = JTBDAnalysis(job_statement=request.text)
        self._emit(context, DiscoveryEventType.JTBD_FRAMED)
        runtime_response = self._synthesize(
            "Frame this as a Jobs-to-be-Done statement, covering functional, emotional, and social "
            f"dimensions: {analysis.job_statement}",
            package,
            context,
        )
        return self._response_from_runtime(
            context, runtime_response, findings=(analysis.job_statement,), sources=self._evidence_ids(package)
        )

    def _handle_synthesize_interview(self, request: DiscoveryRequest, context: SpecialistContext) -> SpecialistResponse:
        package = self._gather(request.text, context)
        self.discovery_state.transition(DiscoveryState.STRUCTURING)
        summary = InterviewSummary(summary=request.text, source=request.source, interviewee=request.title)
        finding = self._record_finding(
            summary=summary.summary, source=summary.source, hypothesis=request.hypothesis, context=context
        )
        self._emit(context, DiscoveryEventType.INTERVIEW_SYNTHESIZED)
        runtime_response = self._synthesize(
            f"Extract structured insights from this interview: {summary.summary}", package, context
        )
        insight_text = self._runtime_text(runtime_response) or summary.summary
        insights = InterviewInsights(insights=(insight_text,), supporting_interview=summary.summary)
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=(finding.to_memory_content(), *insights.insights),
            sources=(summary.source,),
        )

    def _handle_assess_opportunity(self, request: DiscoveryRequest, context: SpecialistContext) -> SpecialistResponse:
        query = request.title or request.text
        package = self._gather(query, context)
        self.discovery_state.transition(DiscoveryState.STRUCTURING)
        item = OpportunityItem(
            title=query, description=request.text, linked_job=request.hypothesis, evidence_ids=self._evidence_ids(package)
        )
        opportunities = OpportunityList(items=(item,))
        self._emit(context, DiscoveryEventType.OPPORTUNITY_ASSESSED)
        runtime_response = self._synthesize(
            f"Assess this opportunity using an Opportunity Solution Tree framing: {item.title}", package, context
        )
        return self._response_from_runtime(
            context, runtime_response, findings=tuple(opp.title for opp in opportunities.items), sources=item.evidence_ids
        )

    def _handle_frame_persona(self, request: DiscoveryRequest, context: SpecialistContext) -> SpecialistResponse:
        query = request.title or request.text
        package = self._gather(query, context)
        self.discovery_state.transition(DiscoveryState.STRUCTURING)
        persona = PersonaSummary(
            name=request.title, segment=request.segment, jobs=request.jobs, pains=request.pains, goals=request.goals
        )
        self._emit(context, DiscoveryEventType.PERSONA_FRAMED)
        runtime_response = self._synthesize(
            f"Summarize this persona, grounded in retrieved context: {persona.name}", package, context
        )
        return self._response_from_runtime(
            context, runtime_response, findings=(f"Persona: {persona.name}",), sources=self._evidence_ids(package)
        )

    def _handle_track_hypothesis(self, request: DiscoveryRequest, context: SpecialistContext) -> SpecialistResponse:
        statement = request.hypothesis or request.text
        package = self._gather(statement, context)
        self.discovery_state.transition(DiscoveryState.STRUCTURING)
        status = HypothesisStatus(request.status) if request.status else HypothesisStatus.UNKNOWN
        item = HypothesisItem(statement=statement, status=status, evidence_ids=self._evidence_ids(package))
        finding = self._record_finding(
            summary=request.text or statement, source=request.source, hypothesis=statement, status=status, context=context
        )
        self._emit(context, DiscoveryEventType.HYPOTHESIS_STATUS_CHANGED, status=status.value)
        runtime_response = self._synthesize(
            f"Summarize the current state of this hypothesis ({status.value}): {statement}", package, context
        )
        return self._response_from_runtime(
            context, runtime_response, findings=(finding.to_memory_content(),), sources=item.evidence_ids
        )

    def _handle_generate_recommendation(self, request: DiscoveryRequest, context: SpecialistContext) -> SpecialistResponse:
        package = self._gather(request.text, context)
        self.discovery_state.transition(DiscoveryState.STRUCTURING)
        evidence_ids = self._evidence_ids(package)
        if evidence_ids:
            recommendation = DiscoveryRecommendation(
                recommendation=request.text or "Proceed based on the available evidence", evidence_ids=evidence_ids
            )
            confidence = 0.7
        else:
            recommendation = DiscoveryRecommendation(
                recommendation="Insufficient evidence to recommend a course of action",
                evidence_gap=f"No prior discovery or research findings found relevant to: {request.text}",
            )
            confidence = 0.1
        self._emit(context, DiscoveryEventType.RECOMMENDATION_GENERATED)
        runtime_response = self._synthesize(
            f"Explain this discovery recommendation, citing the evidence or the evidence gap: "
            f"{recommendation.recommendation}",
            package,
            context,
        )
        return self._response_from_runtime(
            context,
            runtime_response,
            recommendations=(recommendation.recommendation,),
            sources=recommendation.evidence_ids,
            confidence=confidence,
        )

    def _handle_run_discovery_session(self, request: DiscoveryRequest, context: SpecialistContext) -> SpecialistResponse:
        """PRD §9.1's representative Product Discovery Session journey,
        end to end: gather precedent, frame the problem, name hypotheses
        and evidence gaps honestly, produce a structured DiscoveryReport."""
        package = self._gather(request.text, context)
        self.discovery_state.transition(DiscoveryState.STRUCTURING)
        evidence_ids = self._evidence_ids(package)
        hypotheses = (request.hypothesis,) if request.hypothesis else ()
        evidence_gaps = () if evidence_ids else (f"No prior evidence found relevant to: {request.text}",)
        report = DiscoveryReport(problem_statement=request.text, hypotheses=hypotheses, evidence_gaps=evidence_gaps)
        self._emit(context, DiscoveryEventType.DISCOVERY_REPORT_GENERATED)
        runtime_response = self._synthesize(
            f"Produce a structured discovery framing (problem statement, hypotheses, evidence gaps) "
            f"for: {report.problem_statement}",
            package,
            context,
        )
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=(report.problem_statement, *report.hypotheses, *report.evidence_gaps),
            sources=evidence_ids,
            confidence=0.6 if evidence_ids else 0.2,
        )

    def _handle_summarize(self, request: DiscoveryRequest, context: SpecialistContext) -> SpecialistResponse:
        self.discovery_state.transition(DiscoveryState.GATHERING)
        findings = self.memory_service.list_by_memory_type(
            MEMORY_TYPE_DISCOVERY_FINDING,
            organization_id=context.organization_id,
            maximum=self.discovery_policy.default_list_maximum,
        )
        research = self.memory_service.list_by_memory_type(
            MEMORY_TYPE_RESEARCH_FINDING,
            organization_id=context.organization_id,
            maximum=self.discovery_policy.default_list_maximum,
        )
        self._emit(context, DiscoveryEventType.PRECEDENT_RETRIEVED, item_count=len(findings) + len(research))

        self.discovery_state.transition(DiscoveryState.STRUCTURING)
        items = list(findings) + list(research)
        summary_obj = DiscoverySummary(
            summary=f"{len(findings)} discovery finding(s) and {len(research)} research finding(s) on record.",
            finding_count=len(items),
        )
        self._emit(context, DiscoveryEventType.SUMMARY_GENERATED)
        package = ContextPackage(
            sections=[ContextSection(resource_type="memory", items=items)] if items else [],
            estimated_tokens=0,
            item_count=len(items),
            truncated=False,
        )
        runtime_response = self._synthesize("Summarize discovery progress so far.", package, context)
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=(summary_obj.summary,),
            sources=self._ids_from_items(items),
        )

    def _handle_frame_research_question(self, request: DiscoveryRequest, context: SpecialistContext) -> SpecialistResponse:
        if not request.text:
            raise ValueError("A research question requires request.text")
        self.discovery_state.transition(DiscoveryState.STRUCTURING)
        self._emit(context, DiscoveryEventType.RESEARCH_QUESTION_FRAMED, informs=request.informs)
        runtime_response = self._synthesize(
            f"Phrase this as a clear, well-scoped research question: {request.text}", _EMPTY_CONTEXT_PACKAGE, context
        )
        summary = self._runtime_text(runtime_response) or request.text
        metrics = ExecutionMetrics(latency_ms=runtime_response.latency_ms, execution_id=context.execution_id)
        return SpecialistResponse(
            success=runtime_response.success,
            summary=summary,
            confidence=1.0 if runtime_response.success else 0.0,
            execution_metrics=metrics,
            error=runtime_response.error,
            metadata={"informs": request.informs} if request.informs else {},
            **context.shared.identity_fields(),
        )

    def _handle_record_research_finding(self, request: DiscoveryRequest, context: SpecialistContext) -> SpecialistResponse:
        self.discovery_state.transition(DiscoveryState.STRUCTURING)
        finding = ResearchFinding(
            summary=request.text, source_question=request.source_question, implications=request.implications
        )
        self.memory_service.remember_research(
            finding, organization_id=context.organization_id, user_id=context.shared.user_id
        )
        self._emit(context, DiscoveryEventType.RESEARCH_FINDING_RECORDED)
        runtime_response = self._synthesize(
            f"Summarize the product implications of this research finding: {finding.summary}",
            _EMPTY_CONTEXT_PACKAGE,
            context,
        )
        return self._response_from_runtime(
            context, runtime_response, findings=(finding.to_memory_content(),), sources=(request.source_question,)
        )

    def _handle_recall(self, request: DiscoveryRequest, context: SpecialistContext) -> SpecialistResponse:
        self.discovery_state.transition(DiscoveryState.GATHERING)
        package = self.memory_service.recall(
            request.text,
            organization_id=context.organization_id,
            limit=self.discovery_policy.default_recall_limit,
            max_context_tokens=self.discovery_policy.default_max_context_tokens,
        )
        self._emit(context, DiscoveryEventType.PRECEDENT_RETRIEVED, item_count=package.item_count)
        self.discovery_state.transition(DiscoveryState.STRUCTURING)
        self.discovery_state.transition(DiscoveryState.SYNTHESIZING)
        runtime_response = self._generate(request.text or "What do we know from discovery so far?", package, context)
        self._emit(context, DiscoveryEventType.RECALL_COMPLETED, item_count=package.item_count)
        return self._response_from_runtime(context, runtime_response, sources=self._evidence_ids(package))

    # --- shared internal helpers -------------------------------------------------------------

    def _gather(self, query: str, context: SpecialistContext) -> ContextPackage:
        self.discovery_state.transition(DiscoveryState.GATHERING)
        package = self.memory_service.recall(
            query,
            organization_id=context.organization_id,
            limit=self.discovery_policy.default_recall_limit,
            max_context_tokens=self.discovery_policy.default_max_context_tokens,
        )
        self._emit(context, DiscoveryEventType.PRECEDENT_RETRIEVED, item_count=package.item_count)
        return package

    def _record_finding(
        self,
        *,
        summary: str,
        source: str,
        hypothesis: str,
        context: SpecialistContext,
        status: HypothesisStatus = HypothesisStatus.UNKNOWN,
    ) -> DiscoveryFinding:
        finding = DiscoveryFinding(summary=summary, source=source, hypothesis=hypothesis, status=status)
        self.memory_service.remember_discovery(
            finding, organization_id=context.organization_id, user_id=context.shared.user_id
        )
        self._emit(context, DiscoveryEventType.FINDING_RECORDED, memory_type=finding.memory_type)
        return finding

    def _synthesize(self, query: str, package: ContextPackage, context: SpecialistContext) -> RuntimeResponse:
        self.discovery_state.transition(DiscoveryState.SYNTHESIZING)
        return self._generate(query, package, context)

    def _generate(self, query: str, package: ContextPackage, context: SpecialistContext) -> RuntimeResponse:
        prompt_package = PromptBuilder().build(query, package)
        runtime_request = RuntimeRequest(
            organization_id=context.organization_id,
            prompt_package=prompt_package,
            provider=self.default_provider,
            conversation_id=context.conversation_id,
            parent_shared=context.shared,
        )
        return self.coordinator.runtime_adapter.execute(runtime_request)

    @staticmethod
    def _runtime_text(runtime_response: RuntimeResponse) -> str:
        return runtime_response.conversation_response.text if runtime_response.conversation_response else ""

    def _response_from_runtime(
        self,
        context: SpecialistContext,
        runtime_response: RuntimeResponse,
        *,
        findings: tuple[str, ...] = (),
        recommendations: tuple[str, ...] = (),
        sources: tuple[str, ...] = (),
        confidence: float | None = None,
    ) -> SpecialistResponse:
        resolved_confidence = confidence if confidence is not None else 1.0
        metrics = ExecutionMetrics(latency_ms=runtime_response.latency_ms, execution_id=context.execution_id)
        return SpecialistResponse(
            success=runtime_response.success,
            summary=self._runtime_text(runtime_response),
            findings=findings,
            confidence=resolved_confidence if runtime_response.success else 0.0,
            sources=sources,
            recommendations=recommendations,
            execution_metrics=metrics,
            error=runtime_response.error,
            **context.shared.identity_fields(),
        )

    @staticmethod
    def _ids_from_items(items: list[ContextItem]) -> tuple[str, ...]:
        return tuple(str(item.resource_id) for item in items)

    def _evidence_ids(self, package: ContextPackage) -> tuple[str, ...]:
        return tuple(str(item.resource_id) for section in package.sections for item in section.items)

    @staticmethod
    def _extract_request(context: AgentContext) -> DiscoveryRequest:
        extra = context.agent_metadata.extra
        raw = extra.get("discovery_request")
        if isinstance(raw, DiscoveryRequest):
            return raw
        operation_raw = extra.get("operation", DiscoveryOperation.RECALL.value)
        return DiscoveryRequest(
            operation=DiscoveryOperation(operation_raw),
            text=extra.get("text", ""),
            title=extra.get("title", ""),
            source=extra.get("source", ""),
            hypothesis=extra.get("hypothesis", ""),
            status=extra.get("status", ""),
            source_question=extra.get("source_question", ""),
            implications=extra.get("implications", ""),
            informs=extra.get("informs", ""),
            segment=extra.get("segment", ""),
            jobs=tuple(extra.get("jobs", ())),
            pains=tuple(extra.get("pains", ())),
            goals=tuple(extra.get("goals", ())),
        )

    def _emit(self, context: SpecialistContext, event_type: DiscoveryEventType, **data: Any) -> None:
        self.event_publisher.publish(
            DiscoveryEvent(
                event_type=event_type,
                execution_id=context.execution_id,
                correlation_id=context.correlation_id,
                agent_id=self.identity.agent_id,
                data=data,
            )
        )


AgentRegistry.register(_DISCOVERY_AGENT_NAME, DiscoverySpecialist, overwrite=True)
SpecialistRegistry.register(
    _DISCOVERY_AGENT_NAME,
    DiscoverySpecialist,
    specialization="discovery",
    supported_tasks=_SUPPORTED_TASKS,
    overwrite=True,
)
