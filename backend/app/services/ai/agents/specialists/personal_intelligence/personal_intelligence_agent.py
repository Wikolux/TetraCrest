"""PersonalIntelligenceAgent (CP-01) - the Personal Intelligence Pack's
Specialist Agent: identity, goals, projects, reflections, and preferences,
all through the existing Memory Framework, Prompt Builder, and Runtime -
no platform mechanism duplicated or modified.

Two integration paths with the Executive exist, both real, neither
requiring any change to ExecutiveAgent/Dispatcher/ExecutivePlanner (see
docs/08_CAPABILITY_PACKS/CP-01_Personal_Intelligence_Pack/Architecture.md §7):

1. Passive/automatic: anything this agent remembers is written into the
   same Memory Framework ExecutiveAgent's own built-in retrieve_memory
   task already searches - personal context surfaces in ordinary
   Executive conversations with zero delegation to this agent at all.
2. Active/explicit: when a request IS a personal-intelligence operation
   (remember a goal, recall context explicitly, ...), it is delegated to
   this agent, reached via AgentFactory/SpecialistFactory construction and
   AgentExecutor.execute(), the same mechanism every agent in this
   platform is invoked through.

This agent deliberately does NOT declare AgentCapability.MEMORY. The
Executive's own built-in `retrieve_memory`/`retrieve_conversations` tasks
are tagged required_capability=AgentCapability.MEMORY by ExecutivePlanner;
if this agent declared MEMORY too and were present in a caller's
known_agents, Dispatcher.dispatch() would route the Executive's own
internal memory-retrieval steps to this agent instead - and this agent's
SpecialistResponse-shaped output does not satisfy _handle_task's
ContextPackage-shaped expectations for those steps, which would silently
break Executive Agent's own generic chat flow. See Architecture.md §7 for
the full accounting of this collision risk.
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
from app.services.ai.agents.specialists.personal_intelligence.context import build_personal_intelligence_context
from app.services.ai.agents.specialists.personal_intelligence.events import (
    PersonalIntelligenceEvent,
    PersonalIntelligenceEventPublisher,
    PersonalIntelligenceEventType,
)
from app.services.ai.agents.specialists.personal_intelligence.memory_service import PersonalMemoryService
from app.services.ai.agents.specialists.personal_intelligence.planner import PersonalIntelligencePlanner
from app.services.ai.agents.specialists.personal_intelligence.policies import PersonalIntelligencePolicy
from app.services.ai.agents.specialists.personal_intelligence.shared.goal import Goal, GoalCategory, GoalProgressUpdate, GoalStatus
from app.services.ai.agents.specialists.personal_intelligence.shared.identity import IdentityAttribute, IdentityFact
from app.services.ai.agents.specialists.personal_intelligence.shared.preference import Preference
from app.services.ai.agents.specialists.personal_intelligence.shared.project import Project
from app.services.ai.agents.specialists.personal_intelligence.shared.reflection import Reflection, ReflectionPeriod
from app.services.ai.agents.specialists.personal_intelligence.shared.request import (
    PersonalIntelligenceOperation,
    PersonalIntelligenceRequest,
)
from app.services.ai.agents.specialists.personal_intelligence.state import (
    PersonalIntelligenceState,
    PersonalIntelligenceStateMachine,
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
from app.services.context.types import ContextPackage
from app.services.prompt_builder.builder import PromptBuilder

_PERSONAL_INTELLIGENCE_AGENT_NAME = "personal_intelligence"

_SUPPORTED_TASKS: frozenset[SpecialistTaskType] = frozenset({SpecialistTaskType.UNKNOWN})

_DEFAULT_IDENTITY = AgentIdentity(
    agent_id="personal_intelligence",
    name=_PERSONAL_INTELLIGENCE_AGENT_NAME,
    display_name="Personal Intelligence Agent",
    description=(
        "CP-01: maintains a continuous, individually-scoped understanding of "
        "one user - identity, goals, projects, preferences, and reflections - "
        "through the existing Memory Framework, so that understanding "
        "compounds across sessions instead of resetting each time."
    ),
    version="1.0",
    owner="system",
    capabilities=AgentCapabilities(
        declared=frozenset({AgentCapability.PLANNING, AgentCapability.WORKFLOWS, AgentCapability.REASONING})
    ),
    permissions=("specialist:personal_intelligence",),
)

_EMPTY_CONTEXT_PACKAGE = ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)


class PersonalIntelligenceAgent(SpecialistAgent):
    def __init__(
        self,
        identity: AgentIdentity | None = None,
        state_machine: AgentStateMachine | None = None,
        runtime_adapter: RuntimeAdapter | None = None,
        memory_adapter: AgentMemory | None = None,
        tool_adapter: ToolAdapter | None = None,
        planner: PersonalIntelligencePlanner | None = None,
        synthesizer: Any = None,
        policy: SpecialistExecutionPolicy | None = None,
        personal_intelligence_policy: PersonalIntelligencePolicy | None = None,
        event_publisher: PersonalIntelligenceEventPublisher | None = None,
        default_provider: ProviderName = ProviderName.UNKNOWN,
    ) -> None:
        super().__init__(identity or _DEFAULT_IDENTITY, state_machine)
        self.policy = policy or SpecialistExecutionPolicy()
        self.personal_intelligence_policy = personal_intelligence_policy or PersonalIntelligencePolicy()
        resolved_memory = memory_adapter or MemoryAdapter()
        self.memory_service = PersonalMemoryService(resolved_memory)
        self.coordinator = SpecialistCoordinator(
            planner=planner or PersonalIntelligencePlanner(),
            memory_adapter=resolved_memory,
            tool_adapter=tool_adapter or self._default_tool_adapter(),
            runtime_adapter=runtime_adapter or RuntimeAdapter(),
            synthesizer=synthesizer,
        )
        self.event_publisher = event_publisher or PersonalIntelligenceEventPublisher()
        self.default_provider = default_provider
        self.personal_intelligence_state = PersonalIntelligenceStateMachine()
        self._remember_handlers = {
            PersonalIntelligenceOperation.REMEMBER_IDENTITY: self._remember_identity,
            PersonalIntelligenceOperation.REMEMBER_GOAL: self._remember_goal,
            PersonalIntelligenceOperation.UPDATE_GOAL_PROGRESS: self._update_goal_progress,
            PersonalIntelligenceOperation.REMEMBER_PROJECT: self._remember_project,
            PersonalIntelligenceOperation.REMEMBER_REFLECTION: self._remember_reflection,
            PersonalIntelligenceOperation.REMEMBER_PREFERENCE: self._remember_preference,
        }

    def _default_tool_adapter(self) -> ToolAdapter:
        """Mirrors ResearchAgent._default_tool_adapter() exactly: a
        ToolAdapter whose underlying ToolExecutor is actually configured
        from self.policy, so retry_policy/timeout_seconds/maximum_depth
        are not declared fields with no effect. Only used when the caller
        doesn't inject their own tool_adapter."""
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
            raise ValueError("PersonalIntelligenceAgent.execute requires an AgentContext with organization_id set")
        request = self._extract_request(context)
        specialist_request = SpecialistRequest(objective=request.text or request.title)
        specialist_context = build_personal_intelligence_context(context, specialist_request)
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
        return "personal_intelligence"

    def supported_tasks(self) -> frozenset[SpecialistTaskType]:
        return _SUPPORTED_TASKS

    def plan(self, context: SpecialistContext) -> tuple:
        return self.coordinator.planner.plan(context)

    def evaluate(self, response: SpecialistResponse) -> bool:
        return response.success and response.confidence >= self.personal_intelligence_policy.minimum_confidence

    def self_check(self) -> bool:
        return all(
            collaborator is not None
            for collaborator in (
                self.coordinator.planner,
                self.coordinator.memory_adapter,
                self.coordinator.tool_adapter,
                self.coordinator.runtime_adapter,
            )
        )

    def health_check(self) -> bool:
        return self.self_check()

    # --- the rich, Personal-Intelligence-specific entry point -------------------------------

    def process(
        self,
        request: PersonalIntelligenceRequest,
        context: SpecialistContext,
        cancellation_token: CancellationToken | None = None,
    ) -> SpecialistResponse:
        if context.agent_context.delegation_depth >= self.policy.maximum_depth:
            return SpecialistResponse(
                success=False, error="Maximum execution depth exceeded", **context.shared.identity_fields()
            )

        self.personal_intelligence_state.transition(PersonalIntelligenceState.INTERPRETING)
        self._emit(context, PersonalIntelligenceEventType.REQUEST_STARTED)

        try:
            if request.operation == PersonalIntelligenceOperation.RECALL:
                response = self._handle_recall(request, context)
            else:
                self.personal_intelligence_state.transition(PersonalIntelligenceState.PROCESSING)
                response = self._handle_remember(request, context)
        except Exception as exc:  # noqa: BLE001 - a request failure must never crash the caller
            response = SpecialistResponse(success=False, error=str(exc), **context.shared.identity_fields())

        if response.success:
            self.personal_intelligence_state.transition(PersonalIntelligenceState.COMPLETED)
            self._emit(context, PersonalIntelligenceEventType.REQUEST_COMPLETED)
        else:
            self.personal_intelligence_state.transition(PersonalIntelligenceState.FAILED)
            self._emit(context, PersonalIntelligenceEventType.REQUEST_FAILED, error=response.error)
        self.personal_intelligence_state.transition(PersonalIntelligenceState.IDLE)

        return response

    # --- internal helpers ------------------------------------------------------------------

    def _handle_recall(self, request: PersonalIntelligenceRequest, context: SpecialistContext) -> SpecialistResponse:
        self.personal_intelligence_state.transition(PersonalIntelligenceState.RETRIEVING)
        package = self.memory_service.recall(
            request.text,
            organization_id=context.organization_id,
            limit=self.personal_intelligence_policy.default_recall_limit,
            max_context_tokens=self.personal_intelligence_policy.default_max_context_tokens,
        )
        self._emit(context, PersonalIntelligenceEventType.RECALL_COMPLETED, item_count=package.item_count)

        self.personal_intelligence_state.transition(PersonalIntelligenceState.PROCESSING)
        prompt_package = PromptBuilder().build(request.text or "What do you know about me?", package)
        runtime_request = RuntimeRequest(
            organization_id=context.organization_id,
            prompt_package=prompt_package,
            provider=self.default_provider,
            conversation_id=context.conversation_id,
            parent_shared=context.shared,
        )
        runtime_response = self.coordinator.runtime_adapter.execute(runtime_request)
        summary = runtime_response.conversation_response.text if runtime_response.conversation_response else ""
        metrics = ExecutionMetrics(latency_ms=runtime_response.latency_ms, execution_id=context.execution_id)

        return SpecialistResponse(
            success=runtime_response.success,
            summary=summary,
            confidence=1.0 if runtime_response.success else 0.0,
            execution_metrics=metrics,
            error=runtime_response.error,
            **context.shared.identity_fields(),
        )

    def _handle_remember(self, request: PersonalIntelligenceRequest, context: SpecialistContext) -> SpecialistResponse:
        handler = self._remember_handlers.get(request.operation)
        if handler is None:
            return SpecialistResponse(
                success=False, error=f"Unsupported operation: {request.operation!r}", **context.shared.identity_fields()
            )
        organization_id = context.organization_id
        user_id = context.shared.user_id
        summary, event_type = handler(request, organization_id, user_id)
        self._emit(context, event_type)
        return SpecialistResponse(success=True, summary=summary, confidence=1.0, **context.shared.identity_fields())

    def _remember_identity(self, request: PersonalIntelligenceRequest, organization_id: int, user_id: int | None):
        fact = IdentityFact(attribute=IdentityAttribute(request.title), value=request.text)
        self.memory_service.remember_identity(fact, organization_id=organization_id, user_id=user_id)
        return f"Remembered {fact.attribute.value}: {fact.value}", PersonalIntelligenceEventType.IDENTITY_REMEMBERED

    def _remember_goal(self, request: PersonalIntelligenceRequest, organization_id: int, user_id: int | None):
        goal = Goal(
            title=request.title,
            description=request.text,
            category=request.category or GoalCategory.PERSONAL,
            priority=request.priority,
        )
        self.memory_service.remember_goal(goal, organization_id=organization_id, user_id=user_id)
        return f"Remembered goal: {goal.title}", PersonalIntelligenceEventType.GOAL_REMEMBERED

    def _update_goal_progress(self, request: PersonalIntelligenceRequest, organization_id: int, user_id: int | None):
        update = GoalProgressUpdate(
            goal_title=request.title,
            note=request.text,
            new_progress=request.progress,
            new_status=GoalStatus(request.status) if request.status else None,
        )
        self.memory_service.remember_goal_progress(update, organization_id=organization_id, user_id=user_id)
        return f"Recorded progress on '{update.goal_title}'", PersonalIntelligenceEventType.GOAL_PROGRESS_UPDATED

    def _remember_project(self, request: PersonalIntelligenceRequest, organization_id: int, user_id: int | None):
        project = Project(name=request.title, objective=request.text, milestones=request.milestones)
        self.memory_service.remember_project(project, organization_id=organization_id, user_id=user_id)
        return f"Remembered project: {project.name}", PersonalIntelligenceEventType.PROJECT_REMEMBERED

    def _remember_reflection(self, request: PersonalIntelligenceRequest, organization_id: int, user_id: int | None):
        period = ReflectionPeriod(request.category) if request.category else ReflectionPeriod.AD_HOC
        reflection = Reflection(content=request.text, period=period, lessons=request.lessons)
        self.memory_service.remember_reflection(reflection, organization_id=organization_id, user_id=user_id)
        return "Recorded reflection", PersonalIntelligenceEventType.REFLECTION_REMEMBERED

    def _remember_preference(self, request: PersonalIntelligenceRequest, organization_id: int, user_id: int | None):
        preference = Preference(statement=request.text, category=request.category or "general")
        self.memory_service.remember_preference(preference, organization_id=organization_id, user_id=user_id)
        return "Remembered preference", PersonalIntelligenceEventType.PREFERENCE_REMEMBERED

    @staticmethod
    def _extract_request(context: AgentContext) -> PersonalIntelligenceRequest:
        extra = context.agent_metadata.extra
        raw = extra.get("personal_intelligence_request")
        if isinstance(raw, PersonalIntelligenceRequest):
            return raw
        operation_raw = extra.get("operation", PersonalIntelligenceOperation.RECALL.value)
        return PersonalIntelligenceRequest(
            operation=PersonalIntelligenceOperation(operation_raw),
            text=extra.get("text", ""),
            title=extra.get("title", ""),
            category=extra.get("category", ""),
            priority=extra.get("priority", 0),
            progress=extra.get("progress"),
            status=extra.get("status", ""),
            milestones=tuple(extra.get("milestones", ())),
            lessons=tuple(extra.get("lessons", ())),
        )

    def _emit(self, context: SpecialistContext, event_type: PersonalIntelligenceEventType, **data: Any) -> None:
        self.event_publisher.publish(
            PersonalIntelligenceEvent(
                event_type=event_type,
                execution_id=context.execution_id,
                correlation_id=context.correlation_id,
                agent_id=self.identity.agent_id,
                data=data,
            )
        )


AgentRegistry.register(_PERSONAL_INTELLIGENCE_AGENT_NAME, PersonalIntelligenceAgent, overwrite=True)
SpecialistRegistry.register(
    _PERSONAL_INTELLIGENCE_AGENT_NAME,
    PersonalIntelligenceAgent,
    specialization="personal_intelligence",
    supported_tasks=_SUPPORTED_TASKS,
    overwrite=True,
)
