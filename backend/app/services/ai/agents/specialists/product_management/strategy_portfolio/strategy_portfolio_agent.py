"""StrategyPortfolioSpecialist (CP-02, Milestone 6) - roadmap construction
and sequencing, prioritization-framework application at the backlog level,
OKR/North Star Metric structuring, and strategic recommendation generation
(PRD §17), plus a deliberately v1-scoped Portfolio snapshot capability
(PRD §19, Architecture §12).

Built with zero new platform mechanism, mirroring DiscoverySpecialist/
ProductDecisionSpecialist/DeliverySpecialist (Milestones 3-5) exactly:

- Memory: every read/write goes through ProfessionalMemoryService, which
  itself never bypasses AgentMemory. This specialist writes only what ARR
  §3 assigns it - Roadmap State (`RoadmapItem`) and Metric/North Star
  records (`Metric`), both Milestone 1's own domain objects, reused
  unmodified. It never writes a `DecisionRecord` (Product Decision
  Specialist's exclusive write surface, ARR §4 Ownership Matrix) and never
  writes a `DeliveryArtifact` (Delivery Specialist's own).
- Portfolio: per ADR-0006 and Architecture §12, Portfolio is not a
  distinct memory category - `ASSESS_PORTFOLIO` calls the already-existing
  `ProfessionalMemoryService.remember_portfolio()` (Milestone 2), which
  records the portfolio-level view under the already-approved
  `product_roadmap` category. No `product_portfolio` type, or equivalent,
  is introduced anywhere in this milestone.
- Single-product v1 scope (Architecture §12, Implementation_Plan.md
  Milestone 6): `ASSESS_PORTFOLIO` gathers each named product's own
  memory independently and reports a per-product inventory only - it
  never compares products against each other, never detects cross-product
  dependency conflicts, and never scores resource tradeoffs across
  products. That reasoning is a defined, ready extension of this same
  specialist (Architecture §12's own "grain difference, not a separate
  architecture"), not working functionality in this milestone. Every
  `PortfolioAssessment` carries a mandatory `scope_note` so a partial or
  single-product view is never silently presented as a complete portfolio
  analysis (ARR §9's own named anti-pattern).
- Runtime generation: every synthesis goes through AIRuntime via
  RuntimeAdapter, prompts assembled by PromptBuilder - never built by hand.
- Discovery/Decision/Delivery integration: this specialist never imports
  discovery_agent.py, product_decision_agent.py, or delivery_agent.py, and
  never recreates their work. It consumes Discovery Findings, Research
  Findings, Decision Records, Delivery Artifacts, and Roadmap information
  the same way every Memory Framework reader does - through
  ProfessionalMemoryService.recall(), organization-scoped and semantic,
  not type-filtered.
- Evidence discipline: `StrategyRecommendation` cannot be constructed
  without evidence_ids or an explicit evidence_gap, non-empty assumptions/
  trade_offs/risks, a confidence value, and a stated remaining uncertainty
  - "never fabricate strategy" is a property of the type. Unlike Product
  Decision's own `RecommendationReport`, it deliberately has no
  `counterpoint` field: Architecture §12/ARR's own non-responsibility
  boundary is explicit that this specialist "does not itself decide a
  single, one-off decision's outcome with counterpoint discipline" - that
  structural rigor remains exclusively the Product Decision Specialist's.
  `GENERATE_RECOMMENDATION` therefore never writes to memory itself; a
  recommendation that should become a formal decision is the user's
  (or the Executive's) cue to delegate to Product Decision Support.

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
from app.services.ai.agents.specialists.product_management.shared.decision_record import DecisionFramework
from app.services.ai.agents.specialists.product_management.shared.metric import Metric
from app.services.ai.agents.specialists.product_management.shared.portfolio import Portfolio
from app.services.ai.agents.specialists.product_management.shared.roadmap import RoadmapHorizon, RoadmapItem
from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_METRIC, MEMORY_TYPE_ROADMAP
from app.services.ai.agents.specialists.product_management.strategy_portfolio.context import build_strategy_context
from app.services.ai.agents.specialists.product_management.strategy_portfolio.events import (
    StrategyEvent,
    StrategyEventPublisher,
    StrategyEventType,
)
from app.services.ai.agents.specialists.product_management.strategy_portfolio.outputs import (
    InitiativeSequence,
    OKRAssessment,
    OpportunityComparison,
    PortfolioAssessment,
    PrioritizedInitiative,
    ProductVisionAssessment,
    RoadmapEntry,
    RoadmapRecommendation,
    StrategyRecommendation,
    StrategySummary,
    TradeoffAssessment,
)
from app.services.ai.agents.specialists.product_management.strategy_portfolio.planner import StrategyPlanner
from app.services.ai.agents.specialists.product_management.strategy_portfolio.policies import StrategyPolicy
from app.services.ai.agents.specialists.product_management.strategy_portfolio.request import (
    StrategyOperation,
    StrategyRequest,
)
from app.services.ai.agents.specialists.product_management.strategy_portfolio.scoring import (
    ice_score,
    rice_score,
    select_framework,
)
from app.services.ai.agents.specialists.product_management.strategy_portfolio.state import (
    StrategyState,
    StrategyStateMachine,
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

_STRATEGY_AGENT_NAME = "strategy_portfolio"

_SUPPORTED_TASKS: frozenset[SpecialistTaskType] = frozenset({SpecialistTaskType.ANALYSIS})

_DEFAULT_IDENTITY = AgentIdentity(
    agent_id="strategy_portfolio",
    name=_STRATEGY_AGENT_NAME,
    display_name="Strategy & Portfolio Specialist",
    description=(
        "CP-02: executive-level product strategy - roadmap sequencing, backlog-wide prioritization "
        "(RICE/ICE/Kano/Cost of Delay), OKR/North Star Metric structuring, and evidence-backed strategic "
        "recommendations. Portfolio reasoning is deliberately scoped to a per-product inventory in v1 - "
        "cross-product comparison remains a defined, dormant extension (Architecture §12)."
    ),
    version="1.0",
    owner="system",
    capabilities=AgentCapabilities(declared=frozenset({AgentCapability.REASONING, AgentCapability.PLANNING})),
    permissions=("specialist:strategy_portfolio",),
)

_EMPTY_CONTEXT_PACKAGE = ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)


class StrategyPortfolioSpecialist(SpecialistAgent):
    def __init__(
        self,
        identity: AgentIdentity | None = None,
        state_machine: AgentStateMachine | None = None,
        runtime_adapter: RuntimeAdapter | None = None,
        memory_adapter: AgentMemory | None = None,
        tool_adapter: ToolAdapter | None = None,
        planner: StrategyPlanner | None = None,
        synthesizer: Any = None,
        policy: SpecialistExecutionPolicy | None = None,
        strategy_policy: StrategyPolicy | None = None,
        event_publisher: StrategyEventPublisher | None = None,
        memory_service: ProfessionalMemoryService | None = None,
        default_provider: ProviderName = ProviderName.UNKNOWN,
    ) -> None:
        super().__init__(identity or _DEFAULT_IDENTITY, state_machine)
        self.policy = policy or SpecialistExecutionPolicy()
        self.strategy_policy = strategy_policy or StrategyPolicy()
        resolved_memory = memory_adapter or MemoryAdapter()
        self.memory_service = memory_service or ProfessionalMemoryService(resolved_memory)
        self.coordinator = SpecialistCoordinator(
            planner=planner or StrategyPlanner(),
            memory_adapter=resolved_memory,
            tool_adapter=tool_adapter or self._default_tool_adapter(),
            runtime_adapter=runtime_adapter or RuntimeAdapter(),
            synthesizer=synthesizer,
        )
        self.event_publisher = event_publisher or StrategyEventPublisher()
        self.default_provider = default_provider
        self.strategy_state = StrategyStateMachine()
        self._handlers = {
            StrategyOperation.SEQUENCE_ROADMAP: self._handle_sequence_roadmap,
            StrategyOperation.PRIORITIZE_INITIATIVES: self._handle_prioritize_initiatives,
            StrategyOperation.COMPARE_OPPORTUNITIES: self._handle_compare_opportunities,
            StrategyOperation.ASSESS_VISION_ALIGNMENT: self._handle_assess_vision_alignment,
            StrategyOperation.STRUCTURE_NORTH_STAR: self._handle_structure_north_star,
            StrategyOperation.STRUCTURE_OKRS: self._handle_structure_okrs,
            StrategyOperation.ASSESS_TRADEOFFS: self._handle_assess_tradeoffs,
            StrategyOperation.GENERATE_RECOMMENDATION: self._handle_generate_recommendation,
            StrategyOperation.ASSESS_PORTFOLIO: self._handle_assess_portfolio,
            StrategyOperation.SUMMARIZE_STRATEGY: self._handle_summarize_strategy,
            StrategyOperation.RECALL: self._handle_recall,
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
            raise ValueError("StrategyPortfolioSpecialist.execute requires an AgentContext with organization_id set")
        request = self._extract_request(context)
        specialist_request = SpecialistRequest(objective=request.text or request.title)
        specialist_context = build_strategy_context(context, specialist_request)
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
        return "strategy_portfolio"

    def supported_tasks(self) -> frozenset[SpecialistTaskType]:
        return _SUPPORTED_TASKS

    def plan(self, context: SpecialistContext) -> tuple:
        return self.coordinator.planner.plan(context)

    def evaluate(self, response: SpecialistResponse) -> bool:
        return response.success and response.confidence >= self.strategy_policy.minimum_confidence

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

    # --- the rich, Strategy-specific entry point ----------------------------------------------

    def process(
        self,
        request: StrategyRequest,
        context: SpecialistContext,
        cancellation_token: CancellationToken | None = None,
    ) -> SpecialistResponse:
        if context.agent_context.delegation_depth >= self.policy.maximum_depth:
            return SpecialistResponse(
                success=False, error="Maximum execution depth exceeded", **context.shared.identity_fields()
            )

        self.strategy_state.transition(StrategyState.INTERPRETING)
        self._emit(context, StrategyEventType.REQUEST_STARTED)

        handler = self._handlers.get(request.operation)
        try:
            if handler is None:
                raise ValueError(f"Unsupported operation: {request.operation!r}")
            response = handler(request, context)
        except Exception as exc:  # noqa: BLE001 - a request failure must never crash the caller
            if self.strategy_state.can_transition(StrategyState.FAILED):
                self.strategy_state.transition(StrategyState.FAILED)
            response = SpecialistResponse(success=False, error=str(exc), **context.shared.identity_fields())

        if response.success:
            self.strategy_state.transition(StrategyState.COMPLETED)
            self._emit(context, StrategyEventType.REQUEST_COMPLETED)
        else:
            if self.strategy_state.state != StrategyState.FAILED:
                self.strategy_state.transition(StrategyState.FAILED)
            self._emit(context, StrategyEventType.REQUEST_FAILED, error=response.error)
        self.strategy_state.transition(StrategyState.IDLE)

        return response

    # --- operation handlers -----------------------------------------------------------------
    # Every handler leaves strategy_state in SYNTHESIZING when it returns -
    # process() owns the terminal COMPLETED/FAILED transition uniformly.

    def _handle_sequence_roadmap(self, request: StrategyRequest, context: SpecialistContext) -> SpecialistResponse:
        candidates = request.items or ((request.text,) if request.text else ())
        if not candidates:
            raise ValueError("SEQUENCE_ROADMAP requires request.text or request.items naming candidate roadmap items")
        package = self._gather(request.text or ", ".join(candidates), context)
        self.strategy_state.transition(StrategyState.STRUCTURING)
        horizon = request.horizon or RoadmapHorizon.LATER.value
        entries = tuple(
            RoadmapEntry(title=candidate, horizon=horizon, rationale=f"Sequenced at {horizon} horizon")
            for candidate in candidates
        )
        tradeoffs = (
            tuple(f"{candidates[index]} vs {candidates[index + 1]}: relative sequencing" for index in range(len(candidates) - 1))
            if len(candidates) > 1
            else (f"{candidates[0]}: sequenced at {horizon}, deferring alternative sequencing options",)
        )
        recommendation = RoadmapRecommendation(items=entries, tradeoffs=tradeoffs, evidence_ids=self._evidence_ids(package))

        for entry in entries:
            item = RoadmapItem(title=entry.title, horizon=RoadmapHorizon(horizon), product_name=request.product_name)
            self.memory_service.remember_roadmap(item, organization_id=context.organization_id, user_id=context.shared.user_id)
        self._emit(context, StrategyEventType.ROADMAP_REVISED)

        runtime_response = self._synthesize(
            f"Explain this roadmap sequencing at {horizon} horizon: {', '.join(candidates)}", package, context
        )
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=tuple(entry.title for entry in recommendation.items),
            recommendations=recommendation.tradeoffs,
            sources=recommendation.evidence_ids,
        )

    def _handle_prioritize_initiatives(self, request: StrategyRequest, context: SpecialistContext) -> SpecialistResponse:
        candidates = request.items or ((request.text,) if request.text else ())
        query = request.text or ", ".join(candidates)
        package = self._gather(query, context)
        self.strategy_state.transition(StrategyState.STRUCTURING)
        framework = self._select_framework(request)
        score = self._compute_score(framework, request)

        if len(candidates) == 1 and score is not None:
            items = (
                PrioritizedInitiative(
                    name=candidates[0], score=score, rationale=f"{framework.value} score computed from supplied inputs"
                ),
            )
        elif candidates:
            items = tuple(
                PrioritizedInitiative(name=name, rationale="Quantitative inputs not supplied per-item; ranked qualitatively")
                for name in candidates
            )
        else:
            items = ()

        sequence = InitiativeSequence(framework=framework, items=items)
        self._emit(context, StrategyEventType.INITIATIVES_PRIORITIZED)
        runtime_response = self._synthesize(
            f"Explain this {framework.value} prioritization: {', '.join(candidates) or query}", package, context
        )
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=tuple(f"{item.name}: {item.score if item.score is not None else 'unscored'}" for item in sequence.items),
            sources=self._evidence_ids(package),
        )

    def _handle_compare_opportunities(self, request: StrategyRequest, context: SpecialistContext) -> SpecialistResponse:
        if len(request.items) < 2:
            raise ValueError("COMPARE_OPPORTUNITIES requires at least two opportunities to compare")
        package = self._gather(", ".join(request.items), context)
        self.strategy_state.transition(StrategyState.STRUCTURING)
        comparison = OpportunityComparison(options=request.items, evidence_ids=self._evidence_ids(package))
        self._emit(context, StrategyEventType.OPPORTUNITIES_COMPARED)
        runtime_response = self._synthesize(f"Compare these opportunities: {', '.join(request.items)}", package, context)
        return self._response_from_runtime(
            context, runtime_response, findings=comparison.options, sources=comparison.evidence_ids
        )

    def _handle_assess_vision_alignment(self, request: StrategyRequest, context: SpecialistContext) -> SpecialistResponse:
        if not request.text:
            raise ValueError("ASSESS_VISION_ALIGNMENT requires request.text stating the product vision")
        package = self._gather(request.text, context)
        self.strategy_state.transition(StrategyState.STRUCTURING)
        assessment = ProductVisionAssessment(
            vision_statement=request.text, aligned_initiatives=request.items, evidence_ids=self._evidence_ids(package)
        )
        self._emit(context, StrategyEventType.VISION_ALIGNMENT_ASSESSED)
        runtime_response = self._synthesize(
            f"Assess whether these initiatives align with this product vision: {request.text} - "
            f"initiatives: {', '.join(request.items) or '(none supplied)'}",
            package,
            context,
        )
        return self._response_from_runtime(
            context, runtime_response, findings=(assessment.vision_statement, *assessment.aligned_initiatives), sources=assessment.evidence_ids
        )

    def _handle_structure_north_star(self, request: StrategyRequest, context: SpecialistContext) -> SpecialistResponse:
        query = request.title or request.text
        if not query:
            raise ValueError("STRUCTURE_NORTH_STAR requires a title or text naming the metric")
        package = self._gather(query, context)
        self.strategy_state.transition(StrategyState.STRUCTURING)
        metric = Metric(
            name=query, description=request.text if request.title else "", is_north_star=True, product_name=request.product_name
        )
        self.memory_service.remember_metric(metric, organization_id=context.organization_id, user_id=context.shared.user_id)
        self._emit(context, StrategyEventType.NORTH_STAR_STRUCTURED)
        assessment = OKRAssessment(objective=query, north_star=query, evidence_ids=self._evidence_ids(package))
        runtime_response = self._synthesize(f"Explain why this is the product's North Star Metric: {query}", package, context)
        return self._response_from_runtime(
            context, runtime_response, findings=(metric.to_memory_content(),), sources=assessment.evidence_ids
        )

    def _handle_structure_okrs(self, request: StrategyRequest, context: SpecialistContext) -> SpecialistResponse:
        if not request.text:
            raise ValueError("STRUCTURE_OKRS requires request.text stating the objective")
        package = self._gather(request.text, context)
        self.strategy_state.transition(StrategyState.STRUCTURING)
        for key_result in request.key_results:
            metric = Metric(
                name=key_result, description=f"Key result for objective: {request.text}", product_name=request.product_name
            )
            self.memory_service.remember_metric(metric, organization_id=context.organization_id, user_id=context.shared.user_id)
        self._emit(context, StrategyEventType.OKRS_STRUCTURED)
        assessment = OKRAssessment(objective=request.text, key_results=request.key_results, evidence_ids=self._evidence_ids(package))
        runtime_response = self._synthesize(f"Structure this objective and its key results: {request.text}", package, context)
        return self._response_from_runtime(
            context, runtime_response, findings=(assessment.objective, *assessment.key_results), sources=assessment.evidence_ids
        )

    def _handle_assess_tradeoffs(self, request: StrategyRequest, context: SpecialistContext) -> SpecialistResponse:
        query = request.text or ", ".join(request.items)
        if not query:
            raise ValueError("ASSESS_TRADEOFFS requires request.text or request.items")
        package = self._gather(query, context)
        self.strategy_state.transition(StrategyState.STRUCTURING)
        tradeoffs = self._derive_tradeoffs(request)
        assessment = TradeoffAssessment(tradeoffs=tradeoffs, evidence_ids=self._evidence_ids(package))
        self._emit(context, StrategyEventType.TRADEOFFS_ASSESSED)
        runtime_response = self._synthesize(
            f"Analyze these strategic trade-offs: {'; '.join(tradeoffs)}", package, context
        )
        return self._response_from_runtime(
            context, runtime_response, findings=assessment.tradeoffs, sources=assessment.evidence_ids
        )

    def _handle_generate_recommendation(self, request: StrategyRequest, context: SpecialistContext) -> SpecialistResponse:
        if not request.text:
            raise ValueError("GENERATE_RECOMMENDATION requires request.text describing the strategic question")
        package = self._gather(request.text, context)
        self.strategy_state.transition(StrategyState.STRUCTURING)
        evidence_ids = self._evidence_ids(package)
        framework = self._select_framework(request)
        assumptions = self._derive_assumptions(request)
        risks = self._derive_risks(package)
        trade_offs = self._derive_tradeoffs(request)
        confidence = 0.7 if evidence_ids else 0.1
        remaining_uncertainty = self._derive_remaining_uncertainty(evidence_ids)

        if not evidence_ids:
            recommendation = StrategyRecommendation(
                recommendation=(
                    "Insufficient evidence to make a grounded strategic recommendation. Recommend running "
                    "Discovery or Decision Support before proceeding."
                ),
                assumptions=assumptions,
                trade_offs=trade_offs,
                risks=risks,
                confidence=confidence,
                remaining_uncertainty=remaining_uncertainty,
                evidence_gap=f"No prior discovery or decision evidence found relevant to: {request.text}",
            )
            self._emit(context, StrategyEventType.RECOMMENDATION_GENERATED)
            runtime_response = self._synthesize(
                f"Explain honestly why more evidence is needed before a strategic recommendation: {request.text}",
                package,
                context,
            )
            return self._response_from_runtime(
                context, runtime_response, recommendations=(recommendation.recommendation,), confidence=confidence
            )

        recommendation = StrategyRecommendation(
            recommendation=f"Proceed with: {request.title or request.text} (framing: {framework.value})",
            assumptions=assumptions,
            trade_offs=trade_offs,
            risks=risks,
            confidence=confidence,
            remaining_uncertainty=remaining_uncertainty,
            evidence_ids=evidence_ids,
        )
        self._emit(context, StrategyEventType.RECOMMENDATION_GENERATED)
        runtime_response = self._synthesize(f"Summarize this strategic recommendation: {recommendation.recommendation}", package, context)
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=(f"Framework framing: {framework.value}",),
            recommendations=(recommendation.recommendation,),
            sources=evidence_ids,
            confidence=confidence,
        )

    def _handle_assess_portfolio(self, request: StrategyRequest, context: SpecialistContext) -> SpecialistResponse:
        if not request.products:
            raise ValueError("ASSESS_PORTFOLIO requires at least one product name")

        self.strategy_state.transition(StrategyState.GATHERING)
        per_product_notes = []
        all_items: list[ContextItem] = []
        for product in request.products:
            product_package = self.memory_service.recall(
                product,
                organization_id=context.organization_id,
                limit=self.strategy_policy.default_recall_limit,
                max_context_tokens=self.strategy_policy.default_max_context_tokens,
            )
            product_items = [item for section in product_package.sections for item in section.items]
            all_items.extend(product_items)
            note = (
                f"{product}: {len(product_items)} related memory item(s) found"
                if product_items
                else f"{product}: no related memory items found"
            )
            per_product_notes.append(note)
        self._emit(context, StrategyEventType.PRECEDENT_RETRIEVED, item_count=len(all_items))

        self.strategy_state.transition(StrategyState.STRUCTURING)
        scope_note = (
            f"Single-product inventory only, covering {len(request.products)} product(s) individually - no "
            "cross-product comparison, dependency-conflict detection, or resource-tradeoff scoring was "
            "performed (Architecture §12 v1 scope)."
        )
        assessment = PortfolioAssessment(
            products=request.products, per_product_notes=tuple(per_product_notes), scope_note=scope_note
        )

        portfolio = Portfolio(product_names=request.products, priority_notes=scope_note)
        self.memory_service.remember_portfolio(
            portfolio, organization_id=context.organization_id, user_id=context.shared.user_id
        )
        self._emit(context, StrategyEventType.PORTFOLIO_ASSESSED)

        package = ContextPackage(
            sections=[ContextSection(resource_type="memory", items=all_items)] if all_items else [],
            estimated_tokens=0,
            item_count=len(all_items),
            truncated=False,
        )
        runtime_response = self._synthesize(
            f"Summarize this portfolio snapshot, honoring its disclosed scope: {scope_note}", package, context
        )
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=(assessment.scope_note, *assessment.per_product_notes),
            sources=self._ids_from_items(all_items),
        )

    def _handle_summarize_strategy(self, request: StrategyRequest, context: SpecialistContext) -> SpecialistResponse:
        self.strategy_state.transition(StrategyState.GATHERING)
        roadmap_items = list(
            self.memory_service.list_by_memory_type(
                MEMORY_TYPE_ROADMAP, organization_id=context.organization_id, maximum=self.strategy_policy.default_list_maximum
            )
        )
        metrics = list(
            self.memory_service.list_by_memory_type(
                MEMORY_TYPE_METRIC, organization_id=context.organization_id, maximum=self.strategy_policy.default_list_maximum
            )
        )
        self._emit(context, StrategyEventType.PRECEDENT_RETRIEVED, item_count=len(roadmap_items) + len(metrics))

        self.strategy_state.transition(StrategyState.STRUCTURING)
        summary = StrategySummary(
            summary=f"{len(roadmap_items)} roadmap item(s) and {len(metrics)} metric(s) on record.",
            roadmap_item_count=len(roadmap_items),
            metric_count=len(metrics),
        )
        self._emit(context, StrategyEventType.STRATEGY_SUMMARIZED)
        items = roadmap_items + metrics
        package = ContextPackage(
            sections=[ContextSection(resource_type="memory", items=items)] if items else [],
            estimated_tokens=0,
            item_count=len(items),
            truncated=False,
        )
        runtime_response = self._synthesize("Summarize strategy and roadmap progress so far.", package, context)
        return self._response_from_runtime(
            context, runtime_response, findings=(summary.summary,), sources=self._ids_from_items(items)
        )

    def _handle_recall(self, request: StrategyRequest, context: SpecialistContext) -> SpecialistResponse:
        self.strategy_state.transition(StrategyState.GATHERING)
        package = self.memory_service.recall(
            request.text,
            organization_id=context.organization_id,
            limit=self.strategy_policy.default_recall_limit,
            max_context_tokens=self.strategy_policy.default_max_context_tokens,
        )
        self._emit(context, StrategyEventType.PRECEDENT_RETRIEVED, item_count=package.item_count)
        self.strategy_state.transition(StrategyState.STRUCTURING)
        self.strategy_state.transition(StrategyState.SYNTHESIZING)
        runtime_response = self._generate(request.text or "What do we know about strategy so far?", package, context)
        self._emit(context, StrategyEventType.RECALL_COMPLETED, item_count=package.item_count)
        return self._response_from_runtime(context, runtime_response, sources=self._evidence_ids(package))

    # --- strategy-reasoning helpers -----------------------------------------------------------

    def _select_framework(self, request: StrategyRequest) -> DecisionFramework:
        if request.framework:
            return DecisionFramework(request.framework)
        return select_framework(f"{request.text} {request.title}", len(request.items))

    @staticmethod
    def _compute_score(framework: DecisionFramework, request: StrategyRequest) -> float | None:
        if framework == DecisionFramework.RICE:
            return rice_score(request.reach, request.impact, request.confidence_input, request.effort)
        if framework == DecisionFramework.ICE:
            return ice_score(request.impact, request.confidence_input, request.ease)
        return None

    @staticmethod
    def _derive_assumptions(request: StrategyRequest) -> tuple[str, ...]:
        return (
            "No assumptions were explicitly stated by the caller; this recommendation is contingent on "
            "current product and market context remaining as understood.",
        )

    @staticmethod
    def _derive_risks(package: ContextPackage) -> tuple[str, ...]:
        if package.item_count == 0:
            return ("Insufficient evidence retrieved to fully assess this strategic question",)
        return ("No specific risk factors identified from available evidence",)

    @staticmethod
    def _derive_tradeoffs(request: StrategyRequest) -> tuple[str, ...]:
        if len(request.items) >= 2:
            return tuple(f"{request.items[index]} vs {request.items[index + 1]}" for index in range(len(request.items) - 1))
        if request.text:
            return (f"Trade-offs for: {request.text} - not itemized by the caller",)
        return ("No explicit alternatives were supplied to compare trade-offs against.",)

    @staticmethod
    def _derive_remaining_uncertainty(evidence_ids: tuple[str, ...]) -> str:
        if len(evidence_ids) >= 3:
            return "Low - multiple independent evidence items support this recommendation."
        if evidence_ids:
            return "Moderate - limited evidence supports this recommendation; more discovery would strengthen it."
        return "High - no supporting evidence was retrieved."

    # --- shared internal helpers -------------------------------------------------------------

    def _gather(self, query: str, context: SpecialistContext) -> ContextPackage:
        self.strategy_state.transition(StrategyState.GATHERING)
        package = self.memory_service.recall(
            query,
            organization_id=context.organization_id,
            limit=self.strategy_policy.default_recall_limit,
            max_context_tokens=self.strategy_policy.default_max_context_tokens,
        )
        self._emit(context, StrategyEventType.PRECEDENT_RETRIEVED, item_count=package.item_count)
        return package

    def _synthesize(self, query: str, package: ContextPackage, context: SpecialistContext) -> RuntimeResponse:
        self.strategy_state.transition(StrategyState.SYNTHESIZING)
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
    def _extract_request(context: AgentContext) -> StrategyRequest:
        extra = context.agent_metadata.extra
        raw = extra.get("strategy_request")
        if isinstance(raw, StrategyRequest):
            return raw
        operation_raw = extra.get("operation", StrategyOperation.RECALL.value)
        return StrategyRequest(
            operation=StrategyOperation(operation_raw),
            text=extra.get("text", ""),
            title=extra.get("title", ""),
            framework=extra.get("framework", ""),
            items=tuple(extra.get("items", ())),
            products=tuple(extra.get("products", ())),
            key_results=tuple(extra.get("key_results", ())),
            product_name=extra.get("product_name", ""),
            horizon=extra.get("horizon", ""),
            reach=extra.get("reach"),
            impact=extra.get("impact"),
            confidence_input=extra.get("confidence_input"),
            effort=extra.get("effort"),
            ease=extra.get("ease"),
        )

    def _emit(self, context: SpecialistContext, event_type: StrategyEventType, **data: Any) -> None:
        self.event_publisher.publish(
            StrategyEvent(
                event_type=event_type,
                execution_id=context.execution_id,
                correlation_id=context.correlation_id,
                agent_id=self.identity.agent_id,
                data=data,
            )
        )


AgentRegistry.register(_STRATEGY_AGENT_NAME, StrategyPortfolioSpecialist, overwrite=True)
SpecialistRegistry.register(
    _STRATEGY_AGENT_NAME,
    StrategyPortfolioSpecialist,
    specialization="strategy_portfolio",
    supported_tasks=_SUPPORTED_TASKS,
    overwrite=True,
)
