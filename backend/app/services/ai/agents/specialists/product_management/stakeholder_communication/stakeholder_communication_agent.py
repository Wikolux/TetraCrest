"""StakeholderCommunicationSpecialist (CP-02, Milestone 7) - the fifth and
final CP-02 specialist: translates validated product knowledge into
audience-appropriate communication - drafting only, never sending
(Architecture §11, PRD §18).

Built with zero new platform mechanism, mirroring DiscoverySpecialist/
ProductDecisionSpecialist/DeliverySpecialist/StrategyPortfolioSpecialist
(Milestones 3-6) exactly:

- Memory: every read/write goes through ProfessionalMemoryService, which
  itself never bypasses AgentMemory. This specialist writes only what ARR
  §3 assigns it - Stakeholder Records (`Stakeholder`, Milestone 1's own
  type) and drafted communication (`DeliveryArtifact`, Milestone 5's own
  type, tagged `DeliveryArtifactType.COMMUNICATION_DRAFT` - "a
  Delivery-Artifact-shaped record, per §6," ARR's own literal words). It
  never writes a `DecisionRecord`, `RoadmapItem`/`Metric`, or a
  Delivery-owned artifact type - it communicates the other four
  specialists' own output, never originates or duplicates it.
- One pattern, not one per channel (Architecture §11): every one of this
  milestone's twelve named drafting responsibilities (executive summaries
  through portfolio communication) is realized as the single
  `DRAFT_COMMUNICATION` operation, parameterized by `audience`/`purpose` -
  never as twelve near-identical operations or output types. See
  outputs.py's own docstring for the full mapping.
- Runtime generation: every synthesis goes through AIRuntime via
  RuntimeAdapter, prompts assembled by PromptBuilder - never built by hand.
- Discovery/Decision/Delivery/Strategy integration: this specialist never
  imports discovery_agent.py, product_decision_agent.py, delivery_agent.py,
  or strategy_portfolio_agent.py, and never recreates their reasoning. It
  consumes Discovery Findings, Research Findings, Decision Records,
  Delivery Artifacts, Roadmap Items, Metrics, and Portfolio summaries the
  same way every Memory Framework reader does - through
  ProfessionalMemoryService.recall(), organization-scoped and semantic,
  not type-filtered.
- Evidence discipline: `CommunicationDraft` and `DecisionExplanation`
  cannot be constructed without referenced_memory_ids or an explicit
  evidence_gap, and `CommunicationDraft` cannot be constructed without
  non-empty assumptions - "never invents facts" is a property of the
  type. When no evidence is retrieved, `DRAFT_COMMUNICATION` and
  `EXPLAIN_DECISION` never write a `DeliveryArtifact` at all - they
  honestly recommend further Discovery or Decision Support instead (ARR
  §8's own Failure Mode Analysis). When a named stakeholder has no
  Stakeholder Record on file, their role/preference is never invented -
  an honest assumption/placeholder is recorded instead (ARR §8).
- Never sends anything, structurally, not only by policy
  (Implementation_Plan.md Milestone 7's own acceptance criterion): no
  method on this class sends, publishes, or notifies any external
  channel. Every successful draft's own response text says so explicitly
  ("draft ready for review - not sent").

This agent declares `AgentCapability.COMMUNICATION` in addition to
`REASONING`/`PLANNING` - the one capability difference ARR §3 and
Architecture §19 name for this specialist alone among CP-02's five. It
still never declares `AgentCapability.MEMORY` (the same Executive
collision-avoidance reason every CP-02 specialist avoids it) or
`AgentCapability.RESEARCH` (research remains ResearchAgent's alone).
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
from app.services.ai.agents.specialists.product_management.shared.delivery_artifact import (
    DeliveryArtifact,
    DeliveryArtifactType,
)
from app.services.ai.agents.specialists.product_management.shared.stakeholder import RaciRole, Stakeholder
from app.services.ai.agents.specialists.product_management.shared.types import (
    MEMORY_TYPE_DELIVERY_ARTIFACT,
    MEMORY_TYPE_STAKEHOLDER,
)
from app.services.ai.agents.specialists.product_management.stakeholder_communication.context import (
    build_communication_context,
)
from app.services.ai.agents.specialists.product_management.stakeholder_communication.events import (
    CommunicationEvent,
    CommunicationEventPublisher,
    CommunicationEventType,
)
from app.services.ai.agents.specialists.product_management.stakeholder_communication.outputs import (
    CommunicationDraft,
    CommunicationSummary,
    DecisionExplanation,
    StakeholderMappingResult,
)
from app.services.ai.agents.specialists.product_management.stakeholder_communication.planner import CommunicationPlanner
from app.services.ai.agents.specialists.product_management.stakeholder_communication.policies import CommunicationPolicy
from app.services.ai.agents.specialists.product_management.stakeholder_communication.request import (
    StakeholderCommunicationOperation,
    StakeholderCommunicationRequest,
)
from app.services.ai.agents.specialists.product_management.stakeholder_communication.state import (
    CommunicationState,
    CommunicationStateMachine,
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

_COMMUNICATION_AGENT_NAME = "stakeholder_communication"

_SUPPORTED_TASKS: frozenset[SpecialistTaskType] = frozenset({SpecialistTaskType.SUMMARIZATION})

_SUPPORTING_EVIDENCE_LIMIT = 5
_SUPPORTING_EVIDENCE_EXCERPT_LENGTH = 200

_DEFAULT_IDENTITY = AgentIdentity(
    agent_id="stakeholder_communication",
    name=_COMMUNICATION_AGENT_NAME,
    display_name="Stakeholder Communication Specialist",
    description=(
        "CP-02: drafts audience-appropriate stakeholder communication - executive summaries, status "
        "updates, roadmap and portfolio communication, decision explanations, and more - grounded in "
        "actual product knowledge and the user's own voice (CP-01 identity), drafting only, never sending."
    ),
    version="1.0",
    owner="system",
    capabilities=AgentCapabilities(
        declared=frozenset({AgentCapability.REASONING, AgentCapability.PLANNING, AgentCapability.COMMUNICATION})
    ),
    permissions=("specialist:stakeholder_communication",),
)

_EMPTY_CONTEXT_PACKAGE = ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)


class StakeholderCommunicationSpecialist(SpecialistAgent):
    def __init__(
        self,
        identity: AgentIdentity | None = None,
        state_machine: AgentStateMachine | None = None,
        runtime_adapter: RuntimeAdapter | None = None,
        memory_adapter: AgentMemory | None = None,
        tool_adapter: ToolAdapter | None = None,
        planner: CommunicationPlanner | None = None,
        synthesizer: Any = None,
        policy: SpecialistExecutionPolicy | None = None,
        communication_policy: CommunicationPolicy | None = None,
        event_publisher: CommunicationEventPublisher | None = None,
        memory_service: ProfessionalMemoryService | None = None,
        default_provider: ProviderName = ProviderName.UNKNOWN,
    ) -> None:
        super().__init__(identity or _DEFAULT_IDENTITY, state_machine)
        self.policy = policy or SpecialistExecutionPolicy()
        self.communication_policy = communication_policy or CommunicationPolicy()
        resolved_memory = memory_adapter or MemoryAdapter()
        self.memory_service = memory_service or ProfessionalMemoryService(resolved_memory)
        self.coordinator = SpecialistCoordinator(
            planner=planner or CommunicationPlanner(),
            memory_adapter=resolved_memory,
            tool_adapter=tool_adapter or self._default_tool_adapter(),
            runtime_adapter=runtime_adapter or RuntimeAdapter(),
            synthesizer=synthesizer,
        )
        self.event_publisher = event_publisher or CommunicationEventPublisher()
        self.default_provider = default_provider
        self.communication_state = CommunicationStateMachine()
        self._handlers = {
            StakeholderCommunicationOperation.MAP_STAKEHOLDER: self._handle_map_stakeholder,
            StakeholderCommunicationOperation.DRAFT_COMMUNICATION: self._handle_draft_communication,
            StakeholderCommunicationOperation.EXPLAIN_DECISION: self._handle_explain_decision,
            StakeholderCommunicationOperation.SUMMARIZE_COMMUNICATIONS: self._handle_summarize_communications,
            StakeholderCommunicationOperation.RECALL: self._handle_recall,
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
            raise ValueError(
                "StakeholderCommunicationSpecialist.execute requires an AgentContext with organization_id set"
            )
        request = self._extract_request(context)
        specialist_request = SpecialistRequest(objective=request.text or request.title)
        specialist_context = build_communication_context(context, specialist_request)
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
        return "stakeholder_communication"

    def supported_tasks(self) -> frozenset[SpecialistTaskType]:
        return _SUPPORTED_TASKS

    def plan(self, context: SpecialistContext) -> tuple:
        return self.coordinator.planner.plan(context)

    def evaluate(self, response: SpecialistResponse) -> bool:
        return response.success and response.confidence >= self.communication_policy.minimum_confidence

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

    # --- the rich, Stakeholder-Communication-specific entry point ----------------------------

    def process(
        self,
        request: StakeholderCommunicationRequest,
        context: SpecialistContext,
        cancellation_token: CancellationToken | None = None,
    ) -> SpecialistResponse:
        if context.agent_context.delegation_depth >= self.policy.maximum_depth:
            return SpecialistResponse(
                success=False, error="Maximum execution depth exceeded", **context.shared.identity_fields()
            )

        self.communication_state.transition(CommunicationState.INTERPRETING)
        self._emit(context, CommunicationEventType.REQUEST_STARTED)

        handler = self._handlers.get(request.operation)
        try:
            if handler is None:
                raise ValueError(f"Unsupported operation: {request.operation!r}")
            response = handler(request, context)
        except Exception as exc:  # noqa: BLE001 - a request failure must never crash the caller
            if self.communication_state.can_transition(CommunicationState.FAILED):
                self.communication_state.transition(CommunicationState.FAILED)
            response = SpecialistResponse(success=False, error=str(exc), **context.shared.identity_fields())

        if response.success:
            self.communication_state.transition(CommunicationState.COMPLETED)
            self._emit(context, CommunicationEventType.REQUEST_COMPLETED)
        else:
            if self.communication_state.state != CommunicationState.FAILED:
                self.communication_state.transition(CommunicationState.FAILED)
            self._emit(context, CommunicationEventType.REQUEST_FAILED, error=response.error)
        self.communication_state.transition(CommunicationState.IDLE)

        return response

    # --- operation handlers -----------------------------------------------------------------
    # Every handler leaves communication_state in SYNTHESIZING when it
    # returns - process() owns the terminal COMPLETED/FAILED transition
    # uniformly.

    def _handle_map_stakeholder(
        self, request: StakeholderCommunicationRequest, context: SpecialistContext
    ) -> SpecialistResponse:
        name = request.stakeholder_name or request.title
        if not name:
            raise ValueError("MAP_STAKEHOLDER requires stakeholder_name or title naming the stakeholder")
        package = self._gather(name, context)
        self.communication_state.transition(CommunicationState.STRUCTURING)
        raci = RaciRole(request.raci_role) if request.raci_role else None
        stakeholder = Stakeholder(
            name=name,
            role_or_interest=request.role_or_interest,
            raci_role=raci,
            communication_preference=request.communication_preference,
        )
        self.memory_service.remember_stakeholder(
            stakeholder, organization_id=context.organization_id, user_id=context.shared.user_id
        )
        self._emit(context, CommunicationEventType.STAKEHOLDER_MAPPED)
        result = StakeholderMappingResult(
            name=stakeholder.name, raci_role=raci.value if raci else "", role_or_interest=stakeholder.role_or_interest
        )
        runtime_response = self._synthesize(f"Confirm this stakeholder mapping: {stakeholder.to_memory_content()}", package, context)
        return self._response_from_runtime(
            context,
            runtime_response,
            findings=(stakeholder.to_memory_content(), f"RACI: {result.raci_role or 'unspecified'}"),
            sources=self._evidence_ids(package),
        )

    def _handle_draft_communication(
        self, request: StakeholderCommunicationRequest, context: SpecialistContext
    ) -> SpecialistResponse:
        if not request.text:
            raise ValueError("DRAFT_COMMUNICATION requires request.text describing what to communicate about")
        if not request.audience:
            raise ValueError("DRAFT_COMMUNICATION requires request.audience")
        if not request.purpose:
            raise ValueError("DRAFT_COMMUNICATION requires request.purpose")

        query = f"{request.text} {request.stakeholder_name}".strip()
        package = self._gather(query, context)
        self.communication_state.transition(CommunicationState.STRUCTURING)
        evidence_ids = self._evidence_ids(package)
        has_stakeholder_evidence = self._has_stakeholder_evidence(package)
        assumptions = self._derive_assumptions(request, has_stakeholder_evidence)
        confidence = 0.7 if evidence_ids else 0.1

        if not evidence_ids:
            draft = CommunicationDraft(
                audience=request.audience,
                purpose=request.purpose,
                content=(
                    "Insufficient evidence to draft this communication grounded in actual product "
                    "knowledge. Recommend running Discovery or Decision Support first."
                ),
                assumptions=assumptions,
                confidence=confidence,
                evidence_gap=f"No prior product knowledge found relevant to: {request.text}",
            )
            self._emit(context, CommunicationEventType.UPDATE_DRAFTED)
            runtime_response = self._synthesize(
                f"Explain honestly why more evidence is needed before drafting this {request.purpose} for "
                f"a {request.audience} audience: {request.text}",
                package,
                context,
            )
            return self._response_from_runtime(
                context, runtime_response, recommendations=(draft.content,), confidence=confidence
            )

        supporting_evidence = self._supporting_evidence(package)
        runtime_response = self._synthesize(
            f"Draft a {request.purpose} for a {request.audience} audience, grounded in this product "
            f"knowledge: {request.text}",
            package,
            context,
        )
        generated_text = self._runtime_text(runtime_response) or f"{request.purpose} for {request.audience}: {request.text}"
        # Assumptions (including any honest stakeholder-gap placeholder,
        # ARR §8's own required behaviour) must reach the actual draft, not
        # merely exist as an unused, discarded field on the response type.
        content = f"{generated_text} Assumptions: {'; '.join(assumptions)}."
        draft = CommunicationDraft(
            audience=request.audience,
            purpose=request.purpose,
            content=content,
            supporting_evidence=supporting_evidence,
            assumptions=assumptions,
            confidence=confidence,
            referenced_memory_ids=evidence_ids,
        )
        self._emit(context, CommunicationEventType.UPDATE_DRAFTED)

        subject = request.subject or request.title or request.text
        artifact = DeliveryArtifact(
            title=request.title or f"{request.purpose}: {request.text}",
            artifact_type=DeliveryArtifactType.COMMUNICATION_DRAFT,
            content=draft.content,
            feature_title=subject,
            linked_evidence_ids=tuple(int(memory_id) for memory_id in evidence_ids),
        )
        self.memory_service.remember_delivery_artifact(
            artifact, organization_id=context.organization_id, user_id=context.shared.user_id
        )
        self._emit(context, CommunicationEventType.ARTIFACT_STORED)

        return self._response_from_runtime(
            context,
            runtime_response,
            findings=(artifact.to_memory_content(), *draft.assumptions),
            recommendations=(f"Draft ready for review - not sent (audience: {request.audience}).",),
            sources=evidence_ids,
            confidence=confidence,
        )

    def _handle_explain_decision(
        self, request: StakeholderCommunicationRequest, context: SpecialistContext
    ) -> SpecialistResponse:
        query = request.text or request.title
        if not query:
            raise ValueError("EXPLAIN_DECISION requires request.text or request.title naming the decision")
        if not request.audience:
            raise ValueError("EXPLAIN_DECISION requires request.audience")

        package = self._gather(query, context)
        self.communication_state.transition(CommunicationState.STRUCTURING)
        evidence_ids = self._evidence_ids(package)
        has_decision_evidence = self._has_decision_evidence(package)

        if not evidence_ids or not has_decision_evidence:
            confidence = 0.1
            explanation = DecisionExplanation(
                decision_title=query,
                audience=request.audience,
                explanation=(
                    "Insufficient Decision Record evidence retrieved to explain this decision. Recommend "
                    "confirming the decision was recorded via Decision Support first."
                ),
                confidence=confidence,
                evidence_gap=f"No Decision Record found relevant to: {query}",
            )
            self._emit(context, CommunicationEventType.DECISION_EXPLAINED)
            runtime_response = self._synthesize(
                f"Explain honestly why more decision evidence is needed before explaining: {query}", package, context
            )
            return self._response_from_runtime(
                context, runtime_response, recommendations=(explanation.explanation,), confidence=confidence
            )

        confidence = 0.7
        supporting_evidence = self._supporting_evidence(package)
        runtime_response = self._synthesize(f"Explain this decision for a {request.audience} audience: {query}", package, context)
        content = self._runtime_text(runtime_response) or f"Explanation of: {query}"
        explanation = DecisionExplanation(
            decision_title=query,
            audience=request.audience,
            explanation=content,
            supporting_evidence=supporting_evidence,
            referenced_memory_ids=evidence_ids,
            confidence=confidence,
        )
        self._emit(context, CommunicationEventType.DECISION_EXPLAINED)

        artifact = DeliveryArtifact(
            title=f"Decision explanation: {query}",
            artifact_type=DeliveryArtifactType.COMMUNICATION_DRAFT,
            content=content,
            feature_title=request.subject or query,
            linked_evidence_ids=tuple(int(memory_id) for memory_id in evidence_ids),
        )
        self.memory_service.remember_delivery_artifact(
            artifact, organization_id=context.organization_id, user_id=context.shared.user_id
        )
        self._emit(context, CommunicationEventType.ARTIFACT_STORED)

        return self._response_from_runtime(
            context,
            runtime_response,
            findings=(artifact.to_memory_content(),),
            recommendations=("Explanation ready for review - not sent.",),
            sources=evidence_ids,
            confidence=confidence,
        )

    def _handle_summarize_communications(
        self, request: StakeholderCommunicationRequest, context: SpecialistContext
    ) -> SpecialistResponse:
        self.communication_state.transition(CommunicationState.GATHERING)
        stakeholders = list(
            self.memory_service.list_by_memory_type(
                MEMORY_TYPE_STAKEHOLDER,
                organization_id=context.organization_id,
                maximum=self.communication_policy.default_list_maximum,
            )
        )
        artifacts = list(
            self.memory_service.list_by_memory_type(
                MEMORY_TYPE_DELIVERY_ARTIFACT,
                organization_id=context.organization_id,
                maximum=self.communication_policy.default_list_maximum,
            )
        )
        communication_drafts = [
            row for row in artifacts if f"({DeliveryArtifactType.COMMUNICATION_DRAFT.value})" in row.content
        ]
        self._emit(context, CommunicationEventType.PRECEDENT_RETRIEVED, item_count=len(stakeholders) + len(communication_drafts))

        self.communication_state.transition(CommunicationState.STRUCTURING)
        summary = CommunicationSummary(
            summary=f"{len(stakeholders)} stakeholder(s) and {len(communication_drafts)} communication draft(s) on record.",
            stakeholder_count=len(stakeholders),
            draft_count=len(communication_drafts),
        )
        self._emit(context, CommunicationEventType.COMMUNICATIONS_SUMMARIZED)
        items = stakeholders + communication_drafts
        package = ContextPackage(
            sections=[ContextSection(resource_type="memory", items=items)] if items else [],
            estimated_tokens=0,
            item_count=len(items),
            truncated=False,
        )
        runtime_response = self._synthesize("Summarize stakeholder communication activity so far.", package, context)
        return self._response_from_runtime(
            context, runtime_response, findings=(summary.summary,), sources=self._ids_from_items(items)
        )

    def _handle_recall(self, request: StakeholderCommunicationRequest, context: SpecialistContext) -> SpecialistResponse:
        self.communication_state.transition(CommunicationState.GATHERING)
        package = self.memory_service.recall(
            request.text,
            organization_id=context.organization_id,
            limit=self.communication_policy.default_recall_limit,
            max_context_tokens=self.communication_policy.default_max_context_tokens,
        )
        self._emit(context, CommunicationEventType.PRECEDENT_RETRIEVED, item_count=package.item_count)
        self.communication_state.transition(CommunicationState.STRUCTURING)
        self.communication_state.transition(CommunicationState.SYNTHESIZING)
        runtime_response = self._generate(request.text or "What do we know for stakeholder communication so far?", package, context)
        self._emit(context, CommunicationEventType.RECALL_COMPLETED, item_count=package.item_count)
        return self._response_from_runtime(context, runtime_response, sources=self._evidence_ids(package))

    # --- communication-reasoning helpers -------------------------------------------------------

    @staticmethod
    def _derive_assumptions(request: StakeholderCommunicationRequest, has_stakeholder_evidence: bool) -> tuple[str, ...]:
        assumptions: list[str] = []
        if request.stakeholder_name and not has_stakeholder_evidence:
            assumptions.append(
                f"No stakeholder record found for {request.stakeholder_name}; role/preference placeholder "
                "used - confirm before this draft is sent"
            )
        if not assumptions:
            assumptions.append(
                "No assumptions were explicitly stated by the caller; this draft is contingent on current "
                "product and market context remaining as understood."
            )
        return tuple(assumptions)

    @staticmethod
    def _has_stakeholder_evidence(package: ContextPackage) -> bool:
        return any(item.content.startswith("Stakeholder:") for section in package.sections for item in section.items)

    @staticmethod
    def _has_decision_evidence(package: ContextPackage) -> bool:
        return any(item.content.startswith("Decision:") for section in package.sections for item in section.items)

    @staticmethod
    def _supporting_evidence(package: ContextPackage) -> tuple[str, ...]:
        excerpts = [
            item.content[:_SUPPORTING_EVIDENCE_EXCERPT_LENGTH]
            for section in package.sections
            for item in section.items
        ]
        return tuple(excerpts[:_SUPPORTING_EVIDENCE_LIMIT])

    # --- shared internal helpers -------------------------------------------------------------

    def _gather(self, query: str, context: SpecialistContext) -> ContextPackage:
        self.communication_state.transition(CommunicationState.GATHERING)
        package = self.memory_service.recall(
            query,
            organization_id=context.organization_id,
            limit=self.communication_policy.default_recall_limit,
            max_context_tokens=self.communication_policy.default_max_context_tokens,
        )
        self._emit(context, CommunicationEventType.PRECEDENT_RETRIEVED, item_count=package.item_count)
        return package

    def _synthesize(self, query: str, package: ContextPackage, context: SpecialistContext) -> RuntimeResponse:
        self.communication_state.transition(CommunicationState.SYNTHESIZING)
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
    def _extract_request(context: AgentContext) -> StakeholderCommunicationRequest:
        extra = context.agent_metadata.extra
        raw = extra.get("communication_request")
        if isinstance(raw, StakeholderCommunicationRequest):
            return raw
        operation_raw = extra.get("operation", StakeholderCommunicationOperation.RECALL.value)
        return StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation(operation_raw),
            text=extra.get("text", ""),
            title=extra.get("title", ""),
            subject=extra.get("subject", ""),
            audience=extra.get("audience", ""),
            purpose=extra.get("purpose", ""),
            stakeholder_name=extra.get("stakeholder_name", ""),
            role_or_interest=extra.get("role_or_interest", ""),
            raci_role=extra.get("raci_role", ""),
            communication_preference=extra.get("communication_preference", ""),
        )

    def _emit(self, context: SpecialistContext, event_type: CommunicationEventType, **data: Any) -> None:
        self.event_publisher.publish(
            CommunicationEvent(
                event_type=event_type,
                execution_id=context.execution_id,
                correlation_id=context.correlation_id,
                agent_id=self.identity.agent_id,
                data=data,
            )
        )


AgentRegistry.register(_COMMUNICATION_AGENT_NAME, StakeholderCommunicationSpecialist, overwrite=True)
SpecialistRegistry.register(
    _COMMUNICATION_AGENT_NAME,
    StakeholderCommunicationSpecialist,
    specialization="stakeholder_communication",
    supported_tasks=_SUPPORTED_TASKS,
    overwrite=True,
)
