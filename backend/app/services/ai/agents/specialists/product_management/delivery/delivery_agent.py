"""DeliverySpecialist (CP-02, Milestone 5) - turns already-validated,
already-decided product work into drafted delivery artifacts: PRD/spec
drafting, story/epic structuring, acceptance criteria, cross-functional
coordination artifacts, and launch-readiness checks (PRD §16), plus the
PM-facing side of sprint/release framing ARR §9 explicitly approves
("Scrum/Agile delivery cadence awareness ONLY... never engineering-side
ceremony execution, per PRD §4's explicit Non-Goal").

Built with zero new platform mechanism, mirroring DiscoverySpecialist/
ProductDecisionSpecialist (Milestones 3-4) exactly:

- Memory: every read/write goes through ProfessionalMemoryService, which
  itself never bypasses AgentMemory. Delivery Artifacts and Feature/
  Initiative state transitions are both append-only - every write is a
  new entry, never a mutation of a prior one (ARR §6).
- Runtime generation: every synthesis goes through AIRuntime via
  RuntimeAdapter, prompts assembled by PromptBuilder - never built by hand.
- Discovery/Decision integration: this specialist never imports
  discovery_agent.py or product_decision_agent.py, and never recreates
  discovery or decision work. It consumes Discovery Findings, Research
  Findings, Decision Records, and PM Craft Records the same way every
  Memory Framework reader does - through ProfessionalMemoryService.recall(),
  which is organization-scoped and semantic, not type-filtered, so a
  single call naturally surfaces whichever of those four categories is
  relevant, exactly the mechanism Product Decision (Milestone 4) already
  proved reading Discovery's own output through.
- Evidence discipline: DeliveryRecommendation cannot be constructed
  without evidence_ids or an explicit evidence_gap; DeliveryArtifact
  cannot be constructed without linked_evidence_ids and a feature_title
  (ARR §6, Architecture §14). When no evidence is retrieved,
  GENERATE_RECOMMENDATION, GENERATE_ACCEPTANCE_CRITERIA,
  SUPPORT_ENGINEERING_HANDOFF, DECOMPOSE_STORY, BREAKDOWN_EPIC, and
  CHECK_LAUNCH_READINESS never write a DeliveryArtifact at all - they
  still synthesize an honest, evidence-gap-aware response, but skip the
  write rather than persist an artifact that can't cite what grounds it
  (ARR §8's own Failure Mode Analysis: "declined... never presented as
  fully evidenced").
- Artifact-type coverage (Milestone 10 hardening review, ARR §6's "on
  drafting" creation trigger, closed): DECOMPOSE_STORY writes
  DeliveryArtifactType.USER_STORY, BREAKDOWN_EPIC writes
  DeliveryArtifactType.SPEC (an epic breakdown is this specialist's own
  closest fit to the PRD §16 "PRD/spec drafting" capability - no operation
  is dedicated to spec drafting alone), and CHECK_LAUNCH_READINESS writes
  DeliveryArtifactType.LAUNCH_READINESS - closing the gap the Milestone 9
  Production Readiness Report found (all three artifact types were
  declared but never constructed). Every other artifact-writing operation
  in this file already covered its own DeliveryArtifactType member; this
  closes the last three.
- Delivery Confidence Score: this milestone's approved architectural
  enhancement. Every major delivery recommendation (GENERATE_RECOMMENDATION,
  CHECK_LAUNCH_READINESS) exposes a DeliveryConfidenceScore explaining
  itself - which concrete factors were satisfied and which were missing -
  computed deterministically (confidence.py), never a fabricated or
  model-guessed number.

This agent deliberately does NOT declare AgentCapability.MEMORY (the same
Executive collision-avoidance reason every CP-02 specialist avoids it,
Architecture §19) or AgentCapability.RESEARCH (research remains
ResearchAgent's alone - a genuine research need is framed as a question
for the Executive to delegate, never performed here).
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
from app.services.ai.agents.specialists.product_management.delivery.confidence import build_confidence_score
from app.services.ai.agents.specialists.product_management.delivery.context import build_delivery_context
from app.services.ai.agents.specialists.product_management.delivery.events import (
    DeliveryEvent,
    DeliveryEventPublisher,
    DeliveryEventType,
)
from app.services.ai.agents.specialists.product_management.delivery.outputs import (
    ConfidenceFactor,
    DependencyItem,
    DependencyMap,
    DeliveryRecommendation,
    DeliveryRiskItem,
    DeliveryRiskReport,
    EpicPlan,
    RetrospectiveSummary,
    SprintPlan,
    SprintSummary,
    StoryBreakdown,
)
from app.services.ai.agents.specialists.product_management.delivery.planner import DeliveryPlanner
from app.services.ai.agents.specialists.product_management.delivery.policies import DeliveryPolicy
from app.services.ai.agents.specialists.product_management.delivery.request import DeliveryOperation, DeliveryRequest
from app.services.ai.agents.specialists.product_management.delivery.state import DeliveryState, DeliveryStateMachine
from app.services.ai.agents.specialists.product_management.memory_service import ProfessionalMemoryService
from app.services.ai.agents.specialists.product_management.shared.delivery_artifact import (
    DeliveryArtifact,
    DeliveryArtifactType,
)
from app.services.ai.agents.specialists.product_management.shared.feature import FeatureInitiative, FeatureStage
from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_DELIVERY_ARTIFACT, MEMORY_TYPE_FEATURE
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

_DELIVERY_AGENT_NAME = "delivery"

_SUPPORTED_TASKS: frozenset[SpecialistTaskType] = frozenset({SpecialistTaskType.SUMMARIZATION})

_DEFAULT_IDENTITY = AgentIdentity(
    agent_id="delivery",
    name=_DELIVERY_AGENT_NAME,
    display_name="Delivery Specialist",
    description=(
        "CP-02: turns validated, prioritized product work into drafted delivery artifacts - specs, "
        "story/epic structuring, acceptance criteria, sprint framing, launch-readiness checks - always "
        "traceable to the Discovery Finding or Decision Record that grounds it, and always exposing an "
        "explanatory Delivery Confidence Score rather than fabricated certainty."
    ),
    version="1.0",
    owner="system",
    capabilities=AgentCapabilities(declared=frozenset({AgentCapability.REASONING, AgentCapability.PLANNING})),
    permissions=("specialist:delivery",),
)

_EMPTY_CONTEXT_PACKAGE = ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)


class DeliverySpecialist(SpecialistAgent):
    def __init__(
        self,
        identity: AgentIdentity | None = None,
        state_machine: AgentStateMachine | None = None,
        runtime_adapter: RuntimeAdapter | None = None,
        memory_adapter: AgentMemory | None = None,
        tool_adapter: ToolAdapter | None = None,
        planner: DeliveryPlanner | None = None,
        synthesizer: Any = None,
        policy: SpecialistExecutionPolicy | None = None,
        delivery_policy: DeliveryPolicy | None = None,
        event_publisher: DeliveryEventPublisher | None = None,
        memory_service: ProfessionalMemoryService | None = None,
        default_provider: ProviderName = ProviderName.UNKNOWN,
    ) -> None:
        super().__init__(identity or _DEFAULT_IDENTITY, state_machine)
        self.policy = policy or SpecialistExecutionPolicy()
        self.delivery_policy = delivery_policy or DeliveryPolicy()
        resolved_memory = memory_adapter or MemoryAdapter()
        self.memory_service = memory_service or ProfessionalMemoryService(resolved_memory)
        self.coordinator = SpecialistCoordinator(
            planner=planner or DeliveryPlanner(),
            memory_adapter=resolved_memory,
            tool_adapter=tool_adapter or self._default_tool_adapter(),
            runtime_adapter=runtime_adapter or RuntimeAdapter(),
            synthesizer=synthesizer,
        )
        self.event_publisher = event_publisher or DeliveryEventPublisher()
        self.default_provider = default_provider
        self.delivery_state = DeliveryStateMachine()
        self._handlers = {
            DeliveryOperation.PLAN_SPRINT: self._handle_plan_sprint,
            DeliveryOperation.REFINE_BACKLOG: self._handle_refine_backlog,
            DeliveryOperation.DECOMPOSE_STORY: self._handle_decompose_story,
            DeliveryOperation.BREAKDOWN_EPIC: self._handle_breakdown_epic,
            DeliveryOperation.GENERATE_ACCEPTANCE_CRITERIA: self._handle_generate_acceptance_criteria,
            DeliveryOperation.DETECT_DELIVERY_RISKS: self._handle_detect_delivery_risks,
            DeliveryOperation.ANALYZE_DEPENDENCIES: self._handle_analyze_dependencies,
            DeliveryOperation.GENERATE_RECOMMENDATION: self._handle_generate_recommendation,
            DeliveryOperation.SUPPORT_ENGINEERING_HANDOFF: self._handle_support_engineering_handoff,
            DeliveryOperation.SUMMARIZE_DELIVERY: self._handle_summarize_delivery,
            DeliveryOperation.SUPPORT_RETROSPECTIVE: self._handle_support_retrospective,
            DeliveryOperation.CHECK_LAUNCH_READINESS: self._handle_check_launch_readiness,
            DeliveryOperation.RECALL: self._handle_recall,
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
            raise ValueError("DeliverySpecialist.execute requires an AgentContext with organization_id set")
        request = self._extract_request(context)
        specialist_request = SpecialistRequest(objective=request.text or request.title)
        specialist_context = build_delivery_context(context, specialist_request)
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
        return "delivery"

    def supported_tasks(self) -> frozenset[SpecialistTaskType]:
        return _SUPPORTED_TASKS

    def plan(self, context: SpecialistContext) -> tuple:
        return self.coordinator.planner.plan(context)

    def evaluate(self, response: SpecialistResponse) -> bool:
        return response.success and response.confidence >= self.delivery_policy.minimum_confidence

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

    # --- the rich, Delivery-specific entry point ----------------------------------------------

    def process(
        self,
        request: DeliveryRequest,
        context: SpecialistContext,
        cancellation_token: CancellationToken | None = None,
    ) -> SpecialistResponse:
        if context.agent_context.delegation_depth >= self.policy.maximum_depth:
            return SpecialistResponse(
                success=False, error="Maximum execution depth exceeded", **context.shared.identity_fields()
            )

        self.delivery_state.transition(DeliveryState.INTERPRETING)
        self._emit(context, DeliveryEventType.REQUEST_STARTED)

        handler = self._handlers.get(request.operation)
        try:
            if handler is None:
                raise ValueError(f"Unsupported operation: {request.operation!r}")
            response = handler(request, context)
        except Exception as exc:  # noqa: BLE001 - a request failure must never crash the caller
            if self.delivery_state.can_transition(DeliveryState.FAILED):
                self.delivery_state.transition(DeliveryState.FAILED)
            response = SpecialistResponse(success=False, error=str(exc), **context.shared.identity_fields())

        if response.success:
            self.delivery_state.transition(DeliveryState.COMPLETED)
            self._emit(context, DeliveryEventType.REQUEST_COMPLETED)
        else:
            if self.delivery_state.state != DeliveryState.FAILED:
                self.delivery_state.transition(DeliveryState.FAILED)
            self._emit(context, DeliveryEventType.REQUEST_FAILED, error=response.error)
        self.delivery_state.transition(DeliveryState.IDLE)

        return response

    # --- operation handlers -----------------------------------------------------------------
    # Every handler leaves delivery_state in SYNTHESIZING when it returns -
    # process() owns the terminal COMPLETED/FAILED transition uniformly.

    def _handle_plan_sprint(self, request: DeliveryRequest, context: SpecialistContext) -> SpecialistResponse:
        query = request.text or ", ".join(request.items)
        package = self._gather(query, context)
        self.delivery_state.transition(DeliveryState.STRUCTURING)
        sprint_goal = request.text or (f"Deliver: {', '.join(request.items)}" if request.items else "Sprint goal not specified")
        capacity_note = self._capacity_note(request)
        plan = SprintPlan(
            sprint_goal=sprint_goal, items=request.items, capacity_note=capacity_note, evidence_ids=self._evidence_ids(package)
        )
        self._emit(context, DeliveryEventType.SPRINT_PLANNED)
        runtime_response = self._synthesize(f"Draft a PM-facing sprint plan with this goal: {plan.sprint_goal}", package, context)
        return self._response_from_runtime(
            context, runtime_response, findings=(plan.sprint_goal, plan.capacity_note), sources=plan.evidence_ids
        )

    def _handle_refine_backlog(self, request: DeliveryRequest, context: SpecialistContext) -> SpecialistResponse:
        if not request.items:
            raise ValueError("REFINE_BACKLOG requires at least one backlog item")
        package = self._gather(" ".join(request.items), context)
        self.delivery_state.transition(DeliveryState.STRUCTURING)
        evidence_present = bool(self._evidence_ids(package))
        findings = tuple(
            f"{item}: {'evidence-grounded' if evidence_present else 'no linked evidence found - not ready for sprint'}"
            for item in request.items
        )
        self._emit(context, DeliveryEventType.BACKLOG_REFINED)
        runtime_response = self._synthesize(
            f"Assess sprint readiness (never re-prioritize by business value) for: {', '.join(request.items)}", package, context
        )
        return self._response_from_runtime(context, runtime_response, findings=findings, sources=self._evidence_ids(package))

    def _handle_decompose_story(self, request: DeliveryRequest, context: SpecialistContext) -> SpecialistResponse:
        if not request.text:
            raise ValueError("DECOMPOSE_STORY requires request.text describing the feature or spec to decompose")
        package = self._gather(request.text, context)
        self.delivery_state.transition(DeliveryState.STRUCTURING)
        stories = request.items or (request.text,)
        breakdown = StoryBreakdown(parent=request.title or request.text, stories=stories, evidence_ids=self._evidence_ids(package))
        self._emit(context, DeliveryEventType.STORY_DECOMPOSED)
        runtime_response = self._synthesize(f"Structure this into user-facing stories: {request.text}", package, context)
        if breakdown.evidence_ids:
            feature_title = request.feature_title or request.title or request.text
            artifact = DeliveryArtifact(
                title=request.title or f"Stories for: {breakdown.parent}",
                artifact_type=DeliveryArtifactType.USER_STORY,
                content=self._runtime_text(runtime_response) or "; ".join(breakdown.stories),
                feature_title=feature_title,
                linked_evidence_ids=tuple(int(memory_id) for memory_id in breakdown.evidence_ids),
            )
            self.memory_service.remember_delivery_artifact(
                artifact, organization_id=context.organization_id, user_id=context.shared.user_id
            )
            self._emit(context, DeliveryEventType.ARTIFACT_STORED)
        return self._response_from_runtime(context, runtime_response, findings=breakdown.stories, sources=breakdown.evidence_ids)

    def _handle_breakdown_epic(self, request: DeliveryRequest, context: SpecialistContext) -> SpecialistResponse:
        query = request.title or request.text
        if not query:
            raise ValueError("BREAKDOWN_EPIC requires a title or text describing the epic")
        package = self._gather(query, context)
        self.delivery_state.transition(DeliveryState.STRUCTURING)
        plan = EpicPlan(epic_title=query, stories=request.items, evidence_ids=self._evidence_ids(package))
        self._emit(context, DeliveryEventType.EPIC_BROKEN_DOWN)
        runtime_response = self._synthesize(f"Break this epic down into stories: {query}", package, context)
        if plan.evidence_ids:
            feature_title = request.feature_title or query
            artifact = DeliveryArtifact(
                title=plan.epic_title,
                artifact_type=DeliveryArtifactType.SPEC,
                content=self._runtime_text(runtime_response) or "; ".join(plan.stories) or plan.epic_title,
                feature_title=feature_title,
                linked_evidence_ids=tuple(int(memory_id) for memory_id in plan.evidence_ids),
            )
            self.memory_service.remember_delivery_artifact(
                artifact, organization_id=context.organization_id, user_id=context.shared.user_id
            )
            self._emit(context, DeliveryEventType.ARTIFACT_STORED)
        return self._response_from_runtime(
            context, runtime_response, findings=(plan.epic_title, *plan.stories), sources=plan.evidence_ids
        )

    def _handle_generate_acceptance_criteria(
        self, request: DeliveryRequest, context: SpecialistContext
    ) -> SpecialistResponse:
        package = self._gather(request.text, context)
        self.delivery_state.transition(DeliveryState.STRUCTURING)
        evidence_ids = self._evidence_ids(package)
        if not evidence_ids:
            self._emit(context, DeliveryEventType.ACCEPTANCE_CRITERIA_GENERATED)
            runtime_response = self._synthesize(
                f"Explain honestly why more evidence is needed before acceptance criteria can be drafted: {request.text}",
                package,
                context,
            )
            return self._response_from_runtime(
                context,
                runtime_response,
                recommendations=(
                    "Insufficient evidence to draft acceptance criteria tied to the original problem "
                    "statement. Recommend running Discovery or Decision Support first.",
                ),
                confidence=0.1,
            )

        feature_title = request.feature_title or request.title or request.text
        runtime_response = self._synthesize(
            f"Draft clear, testable acceptance criteria tied to this problem statement: {request.text}", package, context
        )
        content = self._runtime_text(runtime_response) or f"Acceptance criteria for: {request.text}"
        artifact = DeliveryArtifact(
            title=request.title or f"Acceptance criteria: {request.text}",
            artifact_type=DeliveryArtifactType.ACCEPTANCE_CRITERIA,
            content=content,
            feature_title=feature_title,
            linked_evidence_ids=tuple(int(memory_id) for memory_id in evidence_ids),
        )
        self.memory_service.remember_delivery_artifact(
            artifact, organization_id=context.organization_id, user_id=context.shared.user_id
        )
        self._emit(context, DeliveryEventType.ARTIFACT_STORED)
        self._emit(context, DeliveryEventType.ACCEPTANCE_CRITERIA_GENERATED)
        return self._response_from_runtime(
            context, runtime_response, findings=(artifact.to_memory_content(),), sources=evidence_ids
        )

    def _handle_detect_delivery_risks(self, request: DeliveryRequest, context: SpecialistContext) -> SpecialistResponse:
        package = self._gather(request.text, context)
        self.delivery_state.transition(DeliveryState.STRUCTURING)
        risks = self._derive_risks(request, package)
        report = DeliveryRiskReport(risks=risks)
        self._emit(context, DeliveryEventType.RISKS_DETECTED)
        runtime_response = self._synthesize(
            f"Summarize these delivery risks: {'; '.join(risk.description for risk in risks)}", package, context
        )
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=tuple(risk.description for risk in report.risks),
            sources=self._evidence_ids(package),
        )

    def _handle_analyze_dependencies(self, request: DeliveryRequest, context: SpecialistContext) -> SpecialistResponse:
        if not request.dependencies:
            raise ValueError("ANALYZE_DEPENDENCIES requires at least one dependency to analyze")
        package = self._gather(" ".join(request.dependencies), context)
        self.delivery_state.transition(DeliveryState.STRUCTURING)
        items = tuple(
            DependencyItem(
                name=dependency,
                mentioned_in_evidence=any(
                    dependency.lower() in item.content.lower() for section in package.sections for item in section.items
                ),
            )
            for dependency in request.dependencies
        )
        dependency_map = DependencyMap(dependencies=items)
        self._emit(context, DeliveryEventType.DEPENDENCIES_ANALYZED)
        runtime_response = self._synthesize(
            f"Analyze these dependencies: {', '.join(request.dependencies)}", package, context
        )
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=tuple(
                f"{dependency.name}: {'evidence found' if dependency.mentioned_in_evidence else 'no evidence found'}"
                for dependency in dependency_map.dependencies
            ),
            sources=self._evidence_ids(package),
        )

    def _handle_generate_recommendation(self, request: DeliveryRequest, context: SpecialistContext) -> SpecialistResponse:
        package = self._gather(request.text, context)
        self.delivery_state.transition(DeliveryState.STRUCTURING)
        evidence_ids = self._evidence_ids(package)
        factors = self._build_confidence_factors(request, package)
        score = build_confidence_score(factors)
        self._emit(context, DeliveryEventType.CONFIDENCE_SCORED, score_percent=score.score_percent)

        if not evidence_ids:
            recommendation = DeliveryRecommendation(
                recommendation=(
                    "Insufficient evidence to make a grounded delivery recommendation. Recommend running "
                    "Discovery or Decision Support before proceeding."
                ),
                confidence=score,
                evidence_gap=f"No prior discovery or decision evidence found relevant to: {request.text}",
            )
            self._emit(context, DeliveryEventType.RECOMMENDATION_GENERATED)
            runtime_response = self._synthesize(
                f"Explain honestly why more discovery/decision evidence is needed before a delivery "
                f"recommendation: {request.text}",
                package,
                context,
            )
            return self._response_from_runtime(
                context,
                runtime_response,
                recommendations=(recommendation.recommendation,),
                confidence=score.score_percent / 100,
            )

        feature_title = request.feature_title or request.title or request.text
        recommendation = DeliveryRecommendation(
            recommendation=f"Proceed with: {request.title or request.text}", confidence=score, evidence_ids=evidence_ids
        )
        self._emit(context, DeliveryEventType.RECOMMENDATION_GENERATED)

        runtime_response = self._synthesize(
            f"Summarize this delivery recommendation and its confidence factors: {recommendation.recommendation}",
            package,
            context,
        )
        content = self._runtime_text(runtime_response) or recommendation.recommendation
        artifact = DeliveryArtifact(
            title=request.title or request.text,
            artifact_type=DeliveryArtifactType.RECOMMENDATION,
            content=content,
            feature_title=feature_title,
            linked_evidence_ids=tuple(int(memory_id) for memory_id in evidence_ids),
        )
        self.memory_service.remember_delivery_artifact(
            artifact, organization_id=context.organization_id, user_id=context.shared.user_id
        )
        self._emit(context, DeliveryEventType.ARTIFACT_STORED)

        if request.stage:
            feature = FeatureInitiative(
                title=feature_title,
                stage=FeatureStage(request.stage),
                linked_evidence_ids=tuple(int(memory_id) for memory_id in evidence_ids),
                product_name=request.product_name,
            )
            self.memory_service.remember_feature(
                feature, organization_id=context.organization_id, user_id=context.shared.user_id
            )
            self._emit(context, DeliveryEventType.FEATURE_STAGE_UPDATED, stage=request.stage)

        return self._response_from_runtime(
            context,
            runtime_response,
            findings=(artifact.to_memory_content(),),
            recommendations=(recommendation.recommendation,),
            sources=evidence_ids,
            confidence=score.score_percent / 100,
        )

    def _handle_support_engineering_handoff(
        self, request: DeliveryRequest, context: SpecialistContext
    ) -> SpecialistResponse:
        package = self._gather(request.text, context)
        self.delivery_state.transition(DeliveryState.STRUCTURING)
        evidence_ids = self._evidence_ids(package)
        if not evidence_ids:
            self._emit(context, DeliveryEventType.HANDOFF_SUPPORTED)
            runtime_response = self._synthesize(
                f"Explain honestly why more evidence is needed before an engineering handoff: {request.text}",
                package,
                context,
            )
            return self._response_from_runtime(
                context,
                runtime_response,
                recommendations=(
                    "Insufficient evidence to prepare an engineering handoff. Recommend running Discovery "
                    "or Decision Support first.",
                ),
                confidence=0.1,
            )

        feature_title = request.feature_title or request.title or request.text
        runtime_response = self._synthesize(
            f"Draft an engineering-facing handoff summary for: {request.text}", package, context
        )
        content = self._runtime_text(runtime_response) or f"Handoff notes for: {request.text}"
        artifact = DeliveryArtifact(
            title=request.title or f"Handoff: {request.text}",
            artifact_type=DeliveryArtifactType.HANDOFF_NOTE,
            content=content,
            feature_title=feature_title,
            linked_evidence_ids=tuple(int(memory_id) for memory_id in evidence_ids),
        )
        self.memory_service.remember_delivery_artifact(
            artifact, organization_id=context.organization_id, user_id=context.shared.user_id
        )
        self._emit(context, DeliveryEventType.ARTIFACT_STORED)
        self._emit(context, DeliveryEventType.HANDOFF_SUPPORTED)
        return self._response_from_runtime(
            context, runtime_response, findings=(artifact.to_memory_content(),), sources=evidence_ids
        )

    def _handle_summarize_delivery(self, request: DeliveryRequest, context: SpecialistContext) -> SpecialistResponse:
        self.delivery_state.transition(DeliveryState.GATHERING)
        artifacts = list(
            self.memory_service.list_by_memory_type(
                MEMORY_TYPE_DELIVERY_ARTIFACT,
                organization_id=context.organization_id,
                maximum=self.delivery_policy.default_list_maximum,
            )
        )
        features = list(
            self.memory_service.list_by_memory_type(
                MEMORY_TYPE_FEATURE, organization_id=context.organization_id, maximum=self.delivery_policy.default_list_maximum
            )
        )
        self._emit(context, DeliveryEventType.PRECEDENT_RETRIEVED, item_count=len(artifacts) + len(features))

        self.delivery_state.transition(DeliveryState.STRUCTURING)
        summary = SprintSummary(
            summary=f"{len(artifacts)} delivery artifact(s) and {len(features)} feature/initiative record(s) on record.",
            artifact_count=len(artifacts),
            feature_count=len(features),
        )
        self._emit(context, DeliveryEventType.DELIVERY_SUMMARIZED)
        items = artifacts + features
        package = ContextPackage(
            sections=[ContextSection(resource_type="memory", items=items)] if items else [],
            estimated_tokens=0,
            item_count=len(items),
            truncated=False,
        )
        runtime_response = self._synthesize("Summarize delivery progress so far.", package, context)
        return self._response_from_runtime(
            context, runtime_response, findings=(summary.summary,), sources=self._ids_from_items(items)
        )

    def _handle_support_retrospective(self, request: DeliveryRequest, context: SpecialistContext) -> SpecialistResponse:
        if not request.planned or not request.actual:
            raise ValueError("SUPPORT_RETROSPECTIVE requires both planned and actual to compare")
        package = self._gather(request.text or ", ".join(request.planned), context)
        self.delivery_state.transition(DeliveryState.STRUCTURING)
        gaps = tuple(item for item in request.planned if item not in request.actual)
        surprises = tuple(item for item in request.actual if item not in request.planned)
        summary_text = f"{len(request.actual)} of {len(request.planned)} planned item(s) delivered."
        retro = RetrospectiveSummary(summary=summary_text, planned=request.planned, actual=request.actual, gaps=gaps, surprises=surprises)
        self._emit(context, DeliveryEventType.RETROSPECTIVE_SUPPORTED)
        runtime_response = self._synthesize(f"Summarize this retrospective: {retro.summary}", package, context)
        content = self._runtime_text(runtime_response) or retro.summary

        evidence_ids = self._evidence_ids(package)
        if evidence_ids:
            feature_title = request.feature_title or request.title or request.text or "Sprint retrospective"
            artifact = DeliveryArtifact(
                title=request.title or "Sprint retrospective",
                artifact_type=DeliveryArtifactType.RETROSPECTIVE,
                content=content,
                feature_title=feature_title,
                linked_evidence_ids=tuple(int(memory_id) for memory_id in evidence_ids),
            )
            self.memory_service.remember_delivery_artifact(
                artifact, organization_id=context.organization_id, user_id=context.shared.user_id
            )
            self._emit(context, DeliveryEventType.ARTIFACT_STORED)

        return self._response_from_runtime(
            context, runtime_response, findings=(retro.summary, *retro.gaps, *retro.surprises), sources=evidence_ids
        )

    def _handle_check_launch_readiness(self, request: DeliveryRequest, context: SpecialistContext) -> SpecialistResponse:
        package = self._gather(request.text, context)
        self.delivery_state.transition(DeliveryState.STRUCTURING)
        factors = self._build_confidence_factors(request, package)
        score = build_confidence_score(factors)
        self._emit(context, DeliveryEventType.CONFIDENCE_SCORED, score_percent=score.score_percent)
        ready = len(score.missing) == 0
        recommendation = (
            "Ready to launch - all checked factors satisfied."
            if ready
            else f"Not ready to launch - missing: {', '.join(factor.label for factor in score.missing)}."
        )
        self._emit(context, DeliveryEventType.LAUNCH_READINESS_CHECKED)
        runtime_response = self._synthesize(f"Explain this launch-readiness assessment: {recommendation}", package, context)
        evidence_ids = self._evidence_ids(package)
        if evidence_ids:
            feature_title = request.feature_title or request.title or request.text
            artifact = DeliveryArtifact(
                title=request.title or f"Launch readiness: {request.text}",
                artifact_type=DeliveryArtifactType.LAUNCH_READINESS,
                content=self._runtime_text(runtime_response) or recommendation,
                feature_title=feature_title,
                linked_evidence_ids=tuple(int(memory_id) for memory_id in evidence_ids),
            )
            self.memory_service.remember_delivery_artifact(
                artifact, organization_id=context.organization_id, user_id=context.shared.user_id
            )
            self._emit(context, DeliveryEventType.ARTIFACT_STORED)
        return self._response_from_runtime(
            context,
            runtime_response,
            recommendations=(recommendation,),
            sources=evidence_ids,
            confidence=score.score_percent / 100,
        )

    def _handle_recall(self, request: DeliveryRequest, context: SpecialistContext) -> SpecialistResponse:
        self.delivery_state.transition(DeliveryState.GATHERING)
        package = self.memory_service.recall(
            request.text,
            organization_id=context.organization_id,
            limit=self.delivery_policy.default_recall_limit,
            max_context_tokens=self.delivery_policy.default_max_context_tokens,
        )
        self._emit(context, DeliveryEventType.PRECEDENT_RETRIEVED, item_count=package.item_count)
        self.delivery_state.transition(DeliveryState.STRUCTURING)
        self.delivery_state.transition(DeliveryState.SYNTHESIZING)
        runtime_response = self._generate(request.text or "What do we know about delivery so far?", package, context)
        self._emit(context, DeliveryEventType.RECALL_COMPLETED, item_count=package.item_count)
        return self._response_from_runtime(context, runtime_response, sources=self._evidence_ids(package))

    # --- delivery-reasoning helpers -----------------------------------------------------------

    @staticmethod
    def _capacity_note(request: DeliveryRequest) -> str:
        if request.capacity is None or request.planned_load is None:
            return "Capacity or planned load not supplied; fit cannot be assessed."
        if request.planned_load <= request.capacity:
            return f"Planned load ({request.planned_load:g}) fits within supplied capacity ({request.capacity:g})."
        return (
            f"Planned load ({request.planned_load:g}) exceeds supplied capacity ({request.capacity:g}) - "
            "recommend descoping."
        )

    @staticmethod
    def _derive_risks(request: DeliveryRequest, package: ContextPackage) -> tuple[DeliveryRiskItem, ...]:
        risks: list[DeliveryRiskItem] = []
        if package.item_count == 0:
            risks.append(DeliveryRiskItem(description="Insufficient evidence retrieved to fully assess delivery risk"))
        if request.capacity is not None and request.planned_load is not None and request.planned_load > request.capacity:
            risks.append(
                DeliveryRiskItem(
                    description=f"Planned load ({request.planned_load:g}) exceeds supplied capacity ({request.capacity:g})",
                    likelihood="high",
                )
            )
        for dependency in request.dependencies:
            risks.append(DeliveryRiskItem(description=f"Unresolved dependency: {dependency}"))
        if not risks:
            risks.append(
                DeliveryRiskItem(
                    description="No specific delivery risk factors identified from available evidence or "
                    "stated dependencies",
                    likelihood="low",
                )
            )
        return tuple(risks)

    def _build_confidence_factors(self, request: DeliveryRequest, package: ContextPackage) -> tuple[ConfidenceFactor, ...]:
        has_discovery = self._has_discovery_evidence(package)
        has_decision = self._has_decision_evidence(package)
        return (
            ConfidenceFactor("Discovery validated", has_discovery, "" if has_discovery else "No Discovery Finding retrieved"),
            ConfidenceFactor("Decision approved", has_decision, "" if has_decision else "No Decision Record retrieved"),
            ConfidenceFactor(
                "Dependencies mapped", bool(request.dependencies), "" if request.dependencies else "No dependencies supplied"
            ),
            ConfidenceFactor(
                "Acceptance criteria complete", bool(request.items), "" if request.items else "No acceptance criteria supplied"
            ),
        )

    @staticmethod
    def _has_discovery_evidence(package: ContextPackage) -> bool:
        return any(
            item.content.startswith("Discovery finding:") for section in package.sections for item in section.items
        )

    @staticmethod
    def _has_decision_evidence(package: ContextPackage) -> bool:
        return any(item.content.startswith("Decision:") for section in package.sections for item in section.items)

    # --- shared internal helpers -------------------------------------------------------------

    def _gather(self, query: str, context: SpecialistContext) -> ContextPackage:
        self.delivery_state.transition(DeliveryState.GATHERING)
        package = self.memory_service.recall(
            query,
            organization_id=context.organization_id,
            limit=self.delivery_policy.default_recall_limit,
            max_context_tokens=self.delivery_policy.default_max_context_tokens,
        )
        self._emit(context, DeliveryEventType.PRECEDENT_RETRIEVED, item_count=package.item_count)
        return package

    def _synthesize(self, query: str, package: ContextPackage, context: SpecialistContext) -> RuntimeResponse:
        self.delivery_state.transition(DeliveryState.SYNTHESIZING)
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
    def _extract_request(context: AgentContext) -> DeliveryRequest:
        extra = context.agent_metadata.extra
        raw = extra.get("delivery_request")
        if isinstance(raw, DeliveryRequest):
            return raw
        operation_raw = extra.get("operation", DeliveryOperation.RECALL.value)
        return DeliveryRequest(
            operation=DeliveryOperation(operation_raw),
            text=extra.get("text", ""),
            title=extra.get("title", ""),
            feature_title=extra.get("feature_title", ""),
            items=tuple(extra.get("items", ())),
            dependencies=tuple(extra.get("dependencies", ())),
            capacity=extra.get("capacity"),
            planned_load=extra.get("planned_load"),
            stage=extra.get("stage", ""),
            product_name=extra.get("product_name", ""),
            planned=tuple(extra.get("planned", ())),
            actual=tuple(extra.get("actual", ())),
        )

    def _emit(self, context: SpecialistContext, event_type: DeliveryEventType, **data: Any) -> None:
        self.event_publisher.publish(
            DeliveryEvent(
                event_type=event_type,
                execution_id=context.execution_id,
                correlation_id=context.correlation_id,
                agent_id=self.identity.agent_id,
                data=data,
            )
        )


AgentRegistry.register(_DELIVERY_AGENT_NAME, DeliverySpecialist, overwrite=True)
SpecialistRegistry.register(
    _DELIVERY_AGENT_NAME,
    DeliverySpecialist,
    specialization="delivery",
    supported_tasks=_SUPPORTED_TASKS,
    overwrite=True,
)
