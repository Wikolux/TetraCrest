"""ProductDecisionSpecialist (CP-02, Milestone 4) - converts validated
discovery evidence into structured product decisions: framework
selection/application (RICE, ICE, Kano, Cost of Delay, build-vs-buy,
sunset checklist - Architecture §8), the mandatory counterpoint step, and
the PM Craft Record byproduct write (Architecture §6/§13).

Built with zero new platform mechanism, mirroring DiscoverySpecialist
(Milestone 3) exactly:

- Memory: every read/write goes through ProfessionalMemoryService, which
  itself never bypasses AgentMemory. Decision Records are append-only -
  GENERATE_RECOMMENDATION always writes a *new* DecisionRecord, never
  mutates a prior one (ARR §6's own convention, already how
  ProfessionalMemoryService.remember_decision() works).
- Runtime generation: every synthesis goes through AIRuntime via
  RuntimeAdapter, prompts assembled by PromptBuilder - never built by hand.
- Research: never performed here, and AgentCapability.RESEARCH is never
  declared. If a decision hinges on facts the user doesn't have, that is
  a research question for the Executive to delegate to ResearchAgent
  (Architecture §9) - this specialist only reasons over what has already
  been retrieved or supplied.
- Discovery integration: this specialist never recreates discovery work.
  It consumes Discovery's output the same way every Memory Framework
  reader does - through the DiscoveryFinding/ResearchFinding content
  Discovery already wrote via ProfessionalMemoryService, retrieved here
  through the identical recall()/list_by_memory_type() surface, or
  supplied directly as free-text request fields (question/options/
  criteria) by the caller. It never imports discovery_agent.py or any of
  Discovery's own output types (Architecture's "no CP-02 specialist reads
  another CP-02 specialist's internals," Implementation_Plan.md §3).
- Evidence discipline: RecommendationReport (outputs.py) cannot be
  constructed without evidence_ids or an explicit evidence_gap,
  non-empty assumptions/risks/trade-offs, a stated expected impact, a
  confidence value, and a stated remaining uncertainty - "never fabricate
  certainty" is a property of the type. When no evidence is retrieved,
  GENERATE_RECOMMENDATION never writes a DecisionRecord at all - it
  returns an honest recommendation to run Discovery first (this
  milestone's own explicit principle), never forcing a decision.

A note on framework vocabulary: Milestone 1's `DecisionFramework` enum
(RICE/ICE/Kano/Cost of Delay/build-vs-buy/sunset checklist) is Architecture
§8's and ARR §9's own closed, approved list ("no new methodology is
introduced" - ARR §9) and is reused here exactly as shipped, never
expanded. This milestone's additional named reasoning lenses (Impact vs
Effort, Weighted Scoring, Value vs Complexity, Decision Matrix, Trade-off
Analysis) are real, working code paths - RICE/ICE are literally weighted,
impact-vs-effort scoring (scoring.py); option comparison is a decision
matrix; ANALYZE_TRADEOFFS produces a Trade-off Analysis - but they are
realized as prompt-framing and output-shaping choices layered on top of
the six approved frameworks, never as new DecisionRecord.framework values.
"Opportunity Scoring" reuses PRIORITIZE_FEATURES against Discovery's own
opportunity output, rather than duplicating Discovery's Opportunity
Solution Tree work.

This agent deliberately does NOT declare AgentCapability.MEMORY (the same
Executive collision-avoidance reason every CP-02 specialist avoids it,
Architecture §19) or AgentCapability.RESEARCH (research remains
ResearchAgent's alone).
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
from app.services.ai.agents.specialists.product_management.memory_service import ProfessionalMemoryService
from app.services.ai.agents.specialists.product_management.product_decision.context import build_decision_context
from app.services.ai.agents.specialists.product_management.product_decision.events import (
    DecisionEvent,
    DecisionEventPublisher,
    DecisionEventType,
)
from app.services.ai.agents.specialists.product_management.product_decision.outputs import (
    AlternativeComparison,
    ConfidenceAssessment,
    DecisionHistorySummary,
    DecisionSummary,
    FrameworkAnalysis,
    OptionScore,
    PrioritizationResult,
    PrioritizedItem,
    RecommendationReport,
    RiskAssessment,
    RiskItem,
    TradeoffReport,
)
from app.services.ai.agents.specialists.product_management.product_decision.planner import DecisionPlanner
from app.services.ai.agents.specialists.product_management.product_decision.policies import DecisionPolicy
from app.services.ai.agents.specialists.product_management.product_decision.request import DecisionOperation, DecisionRequest
from app.services.ai.agents.specialists.product_management.product_decision.scoring import (
    ice_score,
    rice_score,
    select_framework,
)
from app.services.ai.agents.specialists.product_management.product_decision.state import DecisionState, DecisionStateMachine
from app.services.ai.agents.specialists.product_management.shared.decision_record import DecisionFramework, DecisionRecord
from app.services.ai.agents.specialists.product_management.shared.pm_craft_record import PMCraftRecord
from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_DECISION
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

_PRODUCT_DECISION_AGENT_NAME = "product_decision"

_SUPPORTED_TASKS: frozenset[SpecialistTaskType] = frozenset({SpecialistTaskType.COMPARISON})

_DEFAULT_IDENTITY = AgentIdentity(
    agent_id="product_decision",
    name=_PRODUCT_DECISION_AGENT_NAME,
    display_name="Product Decision Specialist",
    description=(
        "CP-02: converts validated discovery evidence into structured product decisions - feature "
        "prioritization, trade-off analysis, and framework-backed recommendations (RICE, ICE, Kano, "
        "Cost of Delay, build-vs-buy, sunset checklist), always with a named framework and a surfaced "
        "counterpoint, never fabricating certainty when evidence is thin."
    ),
    version="1.0",
    owner="system",
    capabilities=AgentCapabilities(declared=frozenset({AgentCapability.REASONING, AgentCapability.PLANNING})),
    permissions=("specialist:product_decision",),
)

_EMPTY_CONTEXT_PACKAGE = ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)


class ProductDecisionSpecialist(SpecialistAgent):
    def __init__(
        self,
        identity: AgentIdentity | None = None,
        state_machine: AgentStateMachine | None = None,
        runtime_adapter: RuntimeAdapter | None = None,
        memory_adapter: AgentMemory | None = None,
        tool_adapter: ToolAdapter | None = None,
        planner: DecisionPlanner | None = None,
        synthesizer: Any = None,
        policy: SpecialistExecutionPolicy | None = None,
        decision_policy: DecisionPolicy | None = None,
        event_publisher: DecisionEventPublisher | None = None,
        memory_service: ProfessionalMemoryService | None = None,
        default_provider: ProviderName = ProviderName.UNKNOWN,
    ) -> None:
        super().__init__(identity or _DEFAULT_IDENTITY, state_machine)
        self.policy = policy or SpecialistExecutionPolicy()
        self.decision_policy = decision_policy or DecisionPolicy()
        resolved_memory = memory_adapter or MemoryAdapter()
        self.memory_service = memory_service or ProfessionalMemoryService(resolved_memory)
        self.coordinator = SpecialistCoordinator(
            planner=planner or DecisionPlanner(),
            memory_adapter=resolved_memory,
            tool_adapter=tool_adapter or self._default_tool_adapter(),
            runtime_adapter=runtime_adapter or RuntimeAdapter(),
            synthesizer=synthesizer,
        )
        self.event_publisher = event_publisher or DecisionEventPublisher()
        self.default_provider = default_provider
        self.decision_state = DecisionStateMachine()
        self._handlers = {
            DecisionOperation.PRIORITIZE_FEATURES: self._handle_prioritize_features,
            DecisionOperation.APPLY_FRAMEWORK: self._handle_apply_framework,
            DecisionOperation.ANALYZE_TRADEOFFS: self._handle_analyze_tradeoffs,
            DecisionOperation.COMPARE_OPTIONS: self._handle_compare_options,
            DecisionOperation.IDENTIFY_RISKS: self._handle_identify_risks,
            DecisionOperation.VALIDATE_ASSUMPTIONS: self._handle_validate_assumptions,
            DecisionOperation.ASSESS_CONFIDENCE: self._handle_assess_confidence,
            DecisionOperation.GENERATE_RECOMMENDATION: self._handle_generate_recommendation,
            DecisionOperation.SUMMARIZE_DECISION: self._handle_summarize_decision,
            DecisionOperation.RECALL_DECISION_HISTORY: self._handle_recall_decision_history,
        }

    def _default_tool_adapter(self) -> ToolAdapter:
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
            raise ValueError("ProductDecisionSpecialist.execute requires an AgentContext with organization_id set")
        request = self._extract_request(context)
        specialist_request = SpecialistRequest(objective=request.question or request.title)
        specialist_context = build_decision_context(context, specialist_request)
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
        return "product_decision"

    def supported_tasks(self) -> frozenset[SpecialistTaskType]:
        return _SUPPORTED_TASKS

    def plan(self, context: SpecialistContext) -> tuple:
        return self.coordinator.planner.plan(context)

    def evaluate(self, response: SpecialistResponse) -> bool:
        return response.success and response.confidence >= self.decision_policy.minimum_confidence

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

    # --- the rich, Product-Decision-specific entry point -------------------------------------

    def process(
        self,
        request: DecisionRequest,
        context: SpecialistContext,
        cancellation_token: CancellationToken | None = None,
    ) -> SpecialistResponse:
        if context.agent_context.delegation_depth >= self.policy.maximum_depth:
            return SpecialistResponse(
                success=False, error="Maximum execution depth exceeded", **context.shared.identity_fields()
            )

        self.decision_state.transition(DecisionState.INTERPRETING)
        self._emit(context, DecisionEventType.REQUEST_STARTED)

        handler = self._handlers.get(request.operation)
        try:
            if handler is None:
                raise ValueError(f"Unsupported operation: {request.operation!r}")
            response = handler(request, context)
        except Exception as exc:  # noqa: BLE001 - a request failure must never crash the caller
            if self.decision_state.can_transition(DecisionState.FAILED):
                self.decision_state.transition(DecisionState.FAILED)
            response = SpecialistResponse(success=False, error=str(exc), **context.shared.identity_fields())

        if response.success:
            self.decision_state.transition(DecisionState.COMPLETED)
            self._emit(context, DecisionEventType.REQUEST_COMPLETED)
        else:
            if self.decision_state.state != DecisionState.FAILED:
                self.decision_state.transition(DecisionState.FAILED)
            self._emit(context, DecisionEventType.REQUEST_FAILED, error=response.error)
        self.decision_state.transition(DecisionState.IDLE)

        return response

    # --- operation handlers -----------------------------------------------------------------
    # Every handler leaves decision_state in SYNTHESIZING when it returns -
    # process() owns the terminal COMPLETED/FAILED transition uniformly.

    def _handle_prioritize_features(self, request: DecisionRequest, context: SpecialistContext) -> SpecialistResponse:
        query = request.question or ", ".join(request.options)
        package = self._gather(query, context)
        self.decision_state.transition(DecisionState.STRUCTURING)
        framework = self._select_framework(request)
        self._emit(context, DecisionEventType.FRAMEWORK_SELECTED, framework=framework.value)

        candidates = request.options or ((request.question,) if request.question else ())
        score = self._compute_score(framework, request)

        if len(candidates) == 1 and score is not None:
            items = (
                PrioritizedItem(
                    name=candidates[0], score=score, rationale=f"{framework.value} score computed from supplied inputs"
                ),
            )
        elif candidates:
            items = tuple(
                PrioritizedItem(name=name, rationale="Quantitative inputs not supplied per-item; ranked qualitatively")
                for name in candidates
            )
        else:
            items = (PrioritizedItem(name=query or "candidate", rationale="No candidates were named"),)

        result = PrioritizationResult(framework=framework, items=items)
        self._emit(context, DecisionEventType.PRIORITIZATION_COMPLETED)
        runtime_response = self._synthesize(
            f"Explain this {framework.value} prioritization: {', '.join(candidates) or query}", package, context
        )
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=tuple(f"{item.name}: {item.score if item.score is not None else 'unscored'}" for item in result.items),
            sources=self._evidence_ids(package),
        )

    def _handle_apply_framework(self, request: DecisionRequest, context: SpecialistContext) -> SpecialistResponse:
        package = self._gather(request.question, context)
        self.decision_state.transition(DecisionState.STRUCTURING)
        framework = self._select_framework(request)
        self._emit(context, DecisionEventType.FRAMEWORK_SELECTED, framework=framework.value)
        score = self._compute_score(framework, request)
        analysis = FrameworkAnalysis(
            framework=framework, approach_notes=f"Applying {framework.value} to: {request.question}", score=score
        )
        runtime_response = self._synthesize(
            f"Apply {framework.value} reasoning to this decision: {request.question}", package, context
        )
        return self._response_from_runtime(
            context, runtime_response, findings=(analysis.approach_notes,), sources=self._evidence_ids(package)
        )

    def _handle_analyze_tradeoffs(self, request: DecisionRequest, context: SpecialistContext) -> SpecialistResponse:
        query = request.question or ", ".join(request.options)
        package = self._gather(query, context)
        self.decision_state.transition(DecisionState.STRUCTURING)
        tradeoffs = self._derive_tradeoffs(request)
        report = TradeoffReport(tradeoffs=tradeoffs, leans_toward=request.options[0] if request.options else "")
        self._emit(context, DecisionEventType.TRADEOFFS_ANALYZED)
        runtime_response = self._synthesize(f"Analyze these trade-offs: {'; '.join(tradeoffs)}", package, context)
        return self._response_from_runtime(
            context, runtime_response, findings=report.tradeoffs, sources=self._evidence_ids(package)
        )

    def _handle_compare_options(self, request: DecisionRequest, context: SpecialistContext) -> SpecialistResponse:
        if len(request.options) < 2:
            raise ValueError("COMPARE_OPTIONS requires at least two options to compare")
        package = self._gather(", ".join(request.options), context)
        self.decision_state.transition(DecisionState.STRUCTURING)
        comparison = AlternativeComparison(options=tuple(OptionScore(name=option) for option in request.options))
        self._emit(context, DecisionEventType.OPTIONS_COMPARED)
        runtime_response = self._synthesize(
            f"Compare these options using a decision-matrix framing: {', '.join(request.options)}", package, context
        )
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=tuple(option.name for option in comparison.options),
            sources=self._evidence_ids(package),
        )

    def _handle_identify_risks(self, request: DecisionRequest, context: SpecialistContext) -> SpecialistResponse:
        package = self._gather(request.question, context)
        self.decision_state.transition(DecisionState.STRUCTURING)
        risks = self._derive_risks(request, package)
        assessment = RiskAssessment(risks=risks)
        self._emit(context, DecisionEventType.RISKS_IDENTIFIED)
        runtime_response = self._synthesize(
            f"Summarize these risks: {'; '.join(risk.description for risk in risks)}", package, context
        )
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=tuple(risk.description for risk in assessment.risks),
            sources=self._evidence_ids(package),
        )

    def _handle_validate_assumptions(self, request: DecisionRequest, context: SpecialistContext) -> SpecialistResponse:
        if not request.assumptions:
            raise ValueError("VALIDATE_ASSUMPTIONS requires at least one assumption to validate")
        package = self._gather(" ".join(request.assumptions), context)
        self.decision_state.transition(DecisionState.STRUCTURING)
        has_evidence = bool(self._evidence_ids(package))
        statuses = tuple(
            f"{assumption}: {'evidence-backed' if has_evidence else 'unvalidated (no supporting evidence found)'}"
            for assumption in request.assumptions
        )
        self._emit(context, DecisionEventType.ASSUMPTIONS_VALIDATED)
        runtime_response = self._synthesize(
            f"Assess these assumptions against retrieved evidence: {'; '.join(request.assumptions)}", package, context
        )
        return self._response_from_runtime(context, runtime_response, findings=statuses, sources=self._evidence_ids(package))

    def _handle_assess_confidence(self, request: DecisionRequest, context: SpecialistContext) -> SpecialistResponse:
        package = self._gather(request.question, context)
        self.decision_state.transition(DecisionState.STRUCTURING)
        evidence_ids = self._evidence_ids(package)
        confidence = 0.7 if evidence_ids else 0.1
        rationale = (
            f"Based on {len(evidence_ids)} retrieved evidence item(s)" if evidence_ids else "No supporting evidence retrieved"
        )
        remaining_uncertainty = self._derive_remaining_uncertainty(evidence_ids)
        assessment = ConfidenceAssessment(confidence=confidence, rationale=rationale, remaining_uncertainty=remaining_uncertainty)
        self._emit(context, DecisionEventType.CONFIDENCE_ASSESSED)
        runtime_response = self._synthesize(f"Explain this confidence assessment: {rationale}", package, context)
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=(assessment.rationale, assessment.remaining_uncertainty),
            sources=evidence_ids,
            confidence=confidence,
        )

    def _handle_generate_recommendation(self, request: DecisionRequest, context: SpecialistContext) -> SpecialistResponse:
        package = self._gather(request.question, context)
        self.decision_state.transition(DecisionState.STRUCTURING)
        evidence_ids = self._evidence_ids(package)
        framework = self._select_framework(request)
        self._emit(context, DecisionEventType.FRAMEWORK_SELECTED, framework=framework.value)

        risks = self._derive_risks(request, package)
        assumptions = self._derive_assumptions(request)
        tradeoffs = self._derive_tradeoffs(request)
        expected_impact = self._derive_expected_impact(evidence_ids)
        confidence = 0.7 if evidence_ids else 0.1
        remaining_uncertainty = self._derive_remaining_uncertainty(evidence_ids)
        counterpoint = self._derive_counterpoint(request, risks)

        if not evidence_ids:
            report = RecommendationReport(
                recommendation=(
                    "Insufficient evidence to make a grounded product decision. Recommend running "
                    "Discovery (problem validation, interview synthesis, or hypothesis tracking) before "
                    "proceeding."
                ),
                framework=framework,
                assumptions=assumptions,
                risks=tuple(risk.description for risk in risks),
                tradeoffs=tradeoffs,
                expected_impact=expected_impact,
                confidence=confidence,
                remaining_uncertainty=remaining_uncertainty,
                evidence_gap=f"No prior discovery or research findings found relevant to: {request.question}",
            )
            self._emit(context, DecisionEventType.DECISION_GENERATED)
            runtime_response = self._synthesize(
                f"Explain honestly why more discovery is needed before deciding: {request.question}", package, context
            )
            return self._response_from_runtime(
                context, runtime_response, recommendations=(report.recommendation,), confidence=confidence
            )

        recommendation_text = f"Proceed with: {request.title or request.question}"
        report = RecommendationReport(
            recommendation=recommendation_text,
            framework=framework,
            assumptions=assumptions,
            risks=tuple(risk.description for risk in risks),
            tradeoffs=tradeoffs,
            expected_impact=expected_impact,
            confidence=confidence,
            remaining_uncertainty=remaining_uncertainty,
            evidence_ids=evidence_ids,
        )
        self._emit(context, DecisionEventType.DECISION_GENERATED)

        decision = DecisionRecord(
            title=request.title or request.question,
            framework=framework,
            rationale=report.recommendation,
            counterpoint=counterpoint,
            supporting_memory_ids=tuple(int(memory_id) for memory_id in evidence_ids),
            options_considered=request.options,
            outcome=request.outcome,
        )
        self.memory_service.remember_decision(decision, organization_id=context.organization_id, user_id=context.shared.user_id)
        self._emit(context, DecisionEventType.DECISION_STORED)

        craft_record = PMCraftRecord(framework=framework, decision_title=decision.title, evidence_count=len(evidence_ids))
        self.memory_service.remember_craft_record(
            craft_record, organization_id=context.organization_id, user_id=context.shared.user_id
        )
        self._emit(context, DecisionEventType.CRAFT_RECORD_STORED)

        runtime_response = self._synthesize(
            f"Summarize this product decision, including its counterpoint: {decision.title}", package, context
        )
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=(decision.to_memory_content(),),
            recommendations=(report.recommendation,),
            sources=evidence_ids,
            confidence=confidence,
        )

    def _handle_summarize_decision(self, request: DecisionRequest, context: SpecialistContext) -> SpecialistResponse:
        query = request.title or request.question
        if not query:
            raise ValueError("SUMMARIZE_DECISION requires a title or question identifying which decision to summarize")
        package = self._gather(query, context)
        self.decision_state.transition(DecisionState.STRUCTURING)
        content = (
            package.sections[0].items[0].content
            if package.sections and package.sections[0].items
            else "No matching decision found on record."
        )
        framework_label = next((fw.value for fw in DecisionFramework if fw.value in content.lower()), "unspecified")
        summary = DecisionSummary(title=query, framework=framework_label, summary=content)
        self._emit(context, DecisionEventType.DECISION_SUMMARIZED)
        runtime_response = self._synthesize(f"Summarize this product decision: {content}", package, context)
        return self._response_from_runtime(
            context, runtime_response, findings=(summary.summary,), sources=self._evidence_ids(package)
        )

    def _handle_recall_decision_history(self, request: DecisionRequest, context: SpecialistContext) -> SpecialistResponse:
        self.decision_state.transition(DecisionState.GATHERING)
        rows = self.memory_service.list_by_memory_type(
            MEMORY_TYPE_DECISION, organization_id=context.organization_id, maximum=self.decision_policy.default_list_maximum
        )
        self._emit(context, DecisionEventType.HISTORY_RETRIEVED, item_count=len(rows))
        self.decision_state.transition(DecisionState.STRUCTURING)
        rows = list(rows)
        frameworks_used = tuple(
            sorted({framework.value for framework in DecisionFramework for row in rows if framework.value in row.content.lower()})
        )
        summary = DecisionHistorySummary(
            summary=f"{len(rows)} decision(s) on record.", decision_count=len(rows), frameworks_used=frameworks_used
        )
        package = ContextPackage(
            sections=[ContextSection(resource_type="memory", items=rows)] if rows else [],
            estimated_tokens=0,
            item_count=len(rows),
            truncated=False,
        )
        runtime_response = self._synthesize("Summarize decision history so far.", package, context)
        return self._response_from_runtime(
            context, runtime_response, findings=(summary.summary,), sources=self._ids_from_items(rows)
        )

    # --- decision-reasoning helpers -----------------------------------------------------------

    def _select_framework(self, request: DecisionRequest) -> DecisionFramework:
        if request.framework:
            return DecisionFramework(request.framework)
        return select_framework(f"{request.question} {request.title}", len(request.options))

    @staticmethod
    def _compute_score(framework: DecisionFramework, request: DecisionRequest) -> float | None:
        if framework == DecisionFramework.RICE:
            return rice_score(request.reach, request.impact, request.confidence_input, request.effort)
        if framework == DecisionFramework.ICE:
            return ice_score(request.impact, request.confidence_input, request.ease)
        return None

    @staticmethod
    def _derive_risks(request: DecisionRequest, package: ContextPackage) -> tuple[RiskItem, ...]:
        risks: list[RiskItem] = []
        if package.item_count == 0:
            risks.append(RiskItem(description="Insufficient evidence retrieved to fully assess this decision"))
        for assumption in request.assumptions:
            risks.append(RiskItem(description=f"Assumption may not hold: {assumption}"))
        if not risks:
            risks.append(
                RiskItem(
                    description="No specific risk factors identified from available evidence or stated assumptions",
                    likelihood="low",
                )
            )
        return tuple(risks)

    @staticmethod
    def _derive_assumptions(request: DecisionRequest) -> tuple[str, ...]:
        if request.assumptions:
            return request.assumptions
        return (
            "No assumptions were explicitly stated by the caller; this recommendation is contingent on "
            "current product and market context remaining as understood.",
        )

    @staticmethod
    def _derive_tradeoffs(request: DecisionRequest) -> tuple[str, ...]:
        if request.criteria and request.options:
            return tuple(f"{criterion}: weighed across {', '.join(request.options)}" for criterion in request.criteria)
        if len(request.options) >= 2:
            return tuple(
                f"{request.options[index]} vs {request.options[index + 1]}" for index in range(len(request.options) - 1)
            )
        return ("No explicit alternative options were supplied to compare trade-offs against.",)

    @staticmethod
    def _derive_expected_impact(evidence_ids: tuple[str, ...]) -> str:
        if evidence_ids:
            return (
                f"Directional impact expected, grounded in {len(evidence_ids)} retrieved evidence item(s); "
                "precise magnitude not quantified without stated metrics."
            )
        return "Impact cannot be estimated without supporting evidence."

    @staticmethod
    def _derive_remaining_uncertainty(evidence_ids: tuple[str, ...]) -> str:
        if len(evidence_ids) >= 3:
            return "Low - multiple independent evidence items support this recommendation."
        if evidence_ids:
            return "Moderate - limited evidence supports this recommendation; more discovery would strengthen it."
        return "High - no supporting evidence was retrieved."

    @staticmethod
    def _derive_counterpoint(request: DecisionRequest, risks: tuple[RiskItem, ...]) -> str:
        if request.counterpoint:
            return request.counterpoint
        return f"Counterpoint (derived from top identified risk): {risks[0].description}"

    # --- shared internal helpers -------------------------------------------------------------

    def _gather(self, query: str, context: SpecialistContext) -> ContextPackage:
        self.decision_state.transition(DecisionState.GATHERING)
        package = self.memory_service.recall(
            query,
            organization_id=context.organization_id,
            limit=self.decision_policy.default_recall_limit,
            max_context_tokens=self.decision_policy.default_max_context_tokens,
        )
        self._emit(context, DecisionEventType.PRECEDENT_RETRIEVED, item_count=package.item_count)
        return package

    def _synthesize(self, query: str, package: ContextPackage, context: SpecialistContext) -> RuntimeResponse:
        self.decision_state.transition(DecisionState.SYNTHESIZING)
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
    def _extract_request(context: AgentContext) -> DecisionRequest:
        extra = context.agent_metadata.extra
        raw = extra.get("decision_request")
        if isinstance(raw, DecisionRequest):
            return raw
        operation_raw = extra.get("operation", DecisionOperation.RECALL_DECISION_HISTORY.value)
        return DecisionRequest(
            operation=DecisionOperation(operation_raw),
            question=extra.get("question", ""),
            title=extra.get("title", ""),
            framework=extra.get("framework", ""),
            options=tuple(extra.get("options", ())),
            criteria=tuple(extra.get("criteria", ())),
            assumptions=tuple(extra.get("assumptions", ())),
            counterpoint=extra.get("counterpoint", ""),
            outcome=extra.get("outcome", ""),
            reach=extra.get("reach"),
            impact=extra.get("impact"),
            confidence_input=extra.get("confidence_input"),
            effort=extra.get("effort"),
            ease=extra.get("ease"),
        )

    def _emit(self, context: SpecialistContext, event_type: DecisionEventType, **data: Any) -> None:
        self.event_publisher.publish(
            DecisionEvent(
                event_type=event_type,
                execution_id=context.execution_id,
                correlation_id=context.correlation_id,
                agent_id=self.identity.agent_id,
                data=data,
            )
        )


AgentRegistry.register(_PRODUCT_DECISION_AGENT_NAME, ProductDecisionSpecialist, overwrite=True)
SpecialistRegistry.register(
    _PRODUCT_DECISION_AGENT_NAME,
    ProductDecisionSpecialist,
    specialization="product_decision",
    supported_tasks=_SUPPORTED_TASKS,
    overwrite=True,
)
