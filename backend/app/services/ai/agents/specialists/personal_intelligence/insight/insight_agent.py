"""InsightAgent (CP-01.3) - Executive Cognition: turns the memories
PersonalIntelligenceAgent (and the user, and the Executive's own ordinary
conversation flow) have already written into the Memory Framework into
durable, explainable personal understanding - recurring patterns, habits,
contradictions, goal alignment, periodic reflections, proactive
recommendations, and an evolving profile summary - without a new memory
store, without changing retrieval behavior, and without modifying any
frozen interface.

Same two integration paths with the Executive as PersonalIntelligenceAgent
(see docs/08_CAPABILITY_PACKS/CP-01_Personal_Intelligence_Pack/Architecture.md §7),
and the identical reasoning for both:

1. Passive/automatic: every Insight this agent produces is remembered
   through the same AgentMemory/Memory table ExecutiveAgent's own
   built-in retrieve_memory task already searches - a recommendation or
   profile summary surfaces in ordinary Executive conversations with zero
   delegation to this agent at all.
2. Active/explicit: an explicit request ("what patterns do you see in my
   life", "give me my weekly reflection") is delegated to this agent, the
   same AgentExecutor.execute() mechanism every agent in this platform is
   invoked through.

This agent deliberately does NOT declare AgentCapability.MEMORY, for the
exact same collision-avoidance reason documented on PersonalIntelligenceAgent:
ExecutivePlanner's built-in retrieve_memory/retrieve_conversations tasks
are tagged required_capability=AgentCapability.MEMORY, and this agent's
SpecialistResponse-shaped output does not fit where those internal steps
expect a raw ContextPackage back.

Detection is deliberately deterministic (InsightEngine, a pure,
no-I/O class - see engine.py), never an LLM call: "every generated
insight must be traceable back to supporting memories rather than
invented" is only true by construction if the thing producing an Insight
cannot hallucinate one. AIRuntime is used in exactly one place here -
RECALL_INSIGHTS, rendering a natural-language answer over already-
generated, already-traceable Insights - mirroring exactly how
PersonalIntelligenceAgent reserves the Runtime for its own RECALL
operation and nowhere else.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentCapability
from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.planner import AgentPlanner
from app.services.ai.agents.registry import AgentRegistry
from app.services.ai.agents.specialists.coordinator import SpecialistCoordinator
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
from app.services.ai.agents.specialists.personal_intelligence.insight.context import build_insight_context
from app.services.ai.agents.specialists.personal_intelligence.insight.engine import InsightEngine
from app.services.ai.agents.specialists.personal_intelligence.insight.events import (
    InsightEvent,
    InsightEventPublisher,
    InsightEventType,
)
from app.services.ai.agents.specialists.personal_intelligence.insight.memory_service import InsightMemoryService
from app.services.ai.agents.specialists.personal_intelligence.insight.planner import InsightPlanner
from app.services.ai.agents.specialists.personal_intelligence.insight.policies import InsightPolicy
from app.services.ai.agents.specialists.personal_intelligence.insight.request import InsightOperation, InsightRequest
from app.services.ai.agents.specialists.personal_intelligence.insight.state import InsightState, InsightStateMachine
from app.services.ai.agents.specialists.personal_intelligence.shared.insight import InsightPeriod
from app.services.ai.agents.specialists.personal_intelligence.shared.types import (
    ALL_MEMORY_TYPES,
    MEMORY_TYPE_GOAL,
    MEMORY_TYPE_PREFERENCE,
    MEMORY_TYPE_PROJECT,
    MEMORY_TYPE_REFLECTION,
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
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.cancellation import CancellationToken
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeRequest, RuntimeResponse
from app.services.ai.tools.execution import ToolExecutor
from app.services.ai.tools.manager import ToolManager
from app.services.ai.tools.policies import ToolExecutionPolicy
from app.services.ai_memory_service import AIMemoryService
from app.services.context.types import ContextItem
from app.services.prompt_builder.builder import PromptBuilder

_INSIGHT_AGENT_NAME = "insight"

_SUPPORTED_TASKS: frozenset[SpecialistTaskType] = frozenset(
    {SpecialistTaskType.ANALYSIS, SpecialistTaskType.SUMMARIZATION}
)

# The raw corpus InsightEngine analyzes is always CP-01's five
# user-authored types - never its own prior output (MEMORY_TYPE_INSIGHT
# is deliberately excluded from ALL_MEMORY_TYPES; see shared/types.py).
_ANALYZABLE_MEMORY_TYPES: frozenset[str] = frozenset(ALL_MEMORY_TYPES)

_DEFAULT_IDENTITY = AgentIdentity(
    agent_id="insight",
    name=_INSIGHT_AGENT_NAME,
    display_name="Insight Engine Agent",
    description=(
        "CP-01.3: Executive Cognition - detects recurring patterns, habits, "
        "contradictions, and goal alignment across a user's remembered "
        "identity/goals/projects/reflections/preferences, and produces "
        "periodic reflections, proactive recommendations, and an evolving "
        "profile summary - every one of them traceable back to the exact "
        "memories it was derived from."
    ),
    version="1.0",
    owner="system",
    capabilities=AgentCapabilities(declared=frozenset({AgentCapability.REASONING, AgentCapability.PLANNING})),
    permissions=("specialist:insight",),
)


class InsightAgent(SpecialistAgent):
    def __init__(
        self,
        identity: AgentIdentity | None = None,
        state_machine: AgentStateMachine | None = None,
        runtime_adapter: RuntimeAdapter | None = None,
        memory_adapter: AgentMemory | None = None,
        memory_service: AIMemoryService | None = None,
        tool_adapter: ToolAdapter | None = None,
        planner: InsightPlanner | None = None,
        synthesizer: Any = None,
        policy: SpecialistExecutionPolicy | None = None,
        insight_policy: InsightPolicy | None = None,
        event_publisher: InsightEventPublisher | None = None,
        default_provider: ProviderName = ProviderName.UNKNOWN,
        engine: InsightEngine | None = None,
    ) -> None:
        super().__init__(identity or _DEFAULT_IDENTITY, state_machine)
        self.policy = policy or SpecialistExecutionPolicy()
        self.insight_policy = insight_policy or InsightPolicy()
        resolved_memory = memory_adapter or MemoryAdapter()
        self.insight_memory_service = InsightMemoryService(resolved_memory, memory_service)
        self.engine = engine or InsightEngine()
        self.coordinator = SpecialistCoordinator(
            planner=planner or InsightPlanner(),
            memory_adapter=resolved_memory,
            tool_adapter=tool_adapter or self._default_tool_adapter(),
            runtime_adapter=runtime_adapter or RuntimeAdapter(),
            synthesizer=synthesizer,
        )
        self.event_publisher = event_publisher or InsightEventPublisher()
        self.default_provider = default_provider
        self.insight_state = InsightStateMachine()
        self._analysis_handlers: dict[InsightOperation, Callable] = {
            InsightOperation.ANALYZE_PATTERNS: self._analyze_patterns,
            InsightOperation.IDENTIFY_HABITS: self._identify_habits,
            InsightOperation.DETECT_CONTRADICTIONS: self._detect_contradictions,
            InsightOperation.MEASURE_ALIGNMENT: self._measure_alignment,
            InsightOperation.GENERATE_PERIODIC_REFLECTION: self._generate_periodic_reflection,
            InsightOperation.GENERATE_RECOMMENDATIONS: self._generate_recommendations,
            InsightOperation.UPDATE_PROFILE: self._update_profile,
        }

    def _default_tool_adapter(self) -> ToolAdapter:
        """Mirrors PersonalIntelligenceAgent._default_tool_adapter()/
        ResearchAgent._default_tool_adapter() exactly - a ToolAdapter whose
        ToolExecutor is actually configured from self.policy. No v1
        InsightAgent operation invokes a tool, but the wiring stays
        consistent with the rest of the pack rather than silently
        diverging."""
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
            raise ValueError("InsightAgent.execute requires an AgentContext with organization_id set")
        request = self._extract_request(context)
        specialist_request = SpecialistRequest(objective=request.query or request.operation.value)
        specialist_context = build_insight_context(context, specialist_request)
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
        return "insight"

    def supported_tasks(self) -> frozenset[SpecialistTaskType]:
        return _SUPPORTED_TASKS

    def plan(self, context: SpecialistContext) -> tuple:
        return self.coordinator.planner.plan(context)

    def evaluate(self, response: SpecialistResponse) -> bool:
        return response.success and response.confidence >= self.insight_policy.minimum_confidence

    def self_check(self) -> bool:
        return all(
            collaborator is not None
            for collaborator in (
                self.coordinator.planner,
                self.coordinator.memory_adapter,
                self.coordinator.tool_adapter,
                self.coordinator.runtime_adapter,
                self.engine,
            )
        )

    def health_check(self) -> bool:
        return self.self_check()

    # --- the rich, Insight-specific entry point ----------------------------------------------

    def process(
        self,
        request: InsightRequest,
        context: SpecialistContext,
        cancellation_token: CancellationToken | None = None,
    ) -> SpecialistResponse:
        if context.agent_context.delegation_depth >= self.policy.maximum_depth:
            return SpecialistResponse(
                success=False, error="Maximum execution depth exceeded", **context.shared.identity_fields()
            )

        self.insight_state.transition(InsightState.INTERPRETING)
        self._emit(context, InsightEventType.REQUEST_STARTED)

        try:
            if request.operation == InsightOperation.RECALL_INSIGHTS:
                response = self._handle_recall(request, context)
            else:
                response = self._handle_analysis(request, context)
        except Exception as exc:  # noqa: BLE001 - a request failure must never crash the caller
            response = SpecialistResponse(success=False, error=str(exc), **context.shared.identity_fields())

        if response.success:
            self.insight_state.transition(InsightState.COMPLETED)
            self._emit(context, InsightEventType.REQUEST_COMPLETED)
        else:
            self.insight_state.transition(InsightState.FAILED)
            self._emit(context, InsightEventType.REQUEST_FAILED, error=response.error)
        self.insight_state.transition(InsightState.IDLE)

        return response

    # --- recall ----------------------------------------------------------------------------

    def _handle_recall(self, request: InsightRequest, context: SpecialistContext) -> SpecialistResponse:
        self.insight_state.transition(InsightState.ANALYZING)
        package = self.insight_memory_service.recall_insights(
            request.query,
            organization_id=context.organization_id,
            limit=self.insight_policy.default_recall_limit,
            max_context_tokens=self.insight_policy.default_max_context_tokens,
        )
        self._emit(context, InsightEventType.RECALL_COMPLETED, item_count=package.item_count)

        prompt_package = PromptBuilder().build(
            request.query or "What patterns or insights do you have about me?", package
        )
        runtime_request = RuntimeRequest(
            organization_id=context.organization_id,
            prompt_package=prompt_package,
            provider=self.default_provider,
            conversation_id=context.conversation_id,
            parent_shared=context.shared,
        )
        runtime_response = self.coordinator.runtime_adapter.execute(runtime_request)
        summary = runtime_response.conversation_response.text if runtime_response.conversation_response else ""

        return SpecialistResponse(
            success=runtime_response.success,
            summary=summary,
            confidence=1.0 if runtime_response.success else 0.0,
            error=runtime_response.error,
            **context.shared.identity_fields(),
        )

    # --- analysis (pattern/habit/contradiction/alignment/reflection/recommendation/profile) -----

    def _handle_analysis(self, request: InsightRequest, context: SpecialistContext) -> SpecialistResponse:
        handler = self._analysis_handlers.get(request.operation)
        if handler is None:
            return SpecialistResponse(
                success=False, error=f"Unsupported operation: {request.operation!r}", **context.shared.identity_fields()
            )

        organization_id = context.organization_id
        user_id = context.shared.user_id
        lookback_days = request.lookback_days or self.insight_policy.default_lookback_days
        maximum = request.maximum_memories_analyzed or self.insight_policy.default_maximum_memories_analyzed
        since = datetime.now(UTC) - timedelta(days=lookback_days)

        self.insight_state.transition(InsightState.GATHERING)
        corpus = self.insight_memory_service.list_memory_facts(
            organization_id, since=since, memory_types=_ANALYZABLE_MEMORY_TYPES, maximum=maximum
        )
        self._emit(context, InsightEventType.CORPUS_GATHERED, item_count=len(corpus))

        self.insight_state.transition(InsightState.ANALYZING)
        by_type = self._split_by_memory_type(corpus)
        insights, summary, event_type = handler(request, corpus, by_type)

        for insight in insights:
            self.insight_memory_service.remember_insight(insight, organization_id=organization_id, user_id=user_id)
        self._emit(context, event_type, insight_count=len(insights))

        confidence = (sum(insight.confidence for insight in insights) / len(insights)) if insights else 0.0
        return SpecialistResponse(
            success=True,
            summary=summary,
            findings=tuple(insight.title for insight in insights),
            confidence=confidence,
            **context.shared.identity_fields(),
        )

    @staticmethod
    def _split_by_memory_type(corpus: tuple[ContextItem, ...]) -> dict[str, tuple[ContextItem, ...]]:
        grouped: dict[str, list[ContextItem]] = defaultdict(list)
        for item in corpus:
            memory_type = (item.metadata or {}).get("memory_type")
            grouped[memory_type].append(item)
        return {memory_type: tuple(items) for memory_type, items in grouped.items()}

    def _analyze_patterns(self, request: InsightRequest, corpus, by_type):
        minimum = request.minimum_occurrences or self.insight_policy.default_pattern_minimum_occurrences
        insights = self.engine.detect_patterns(corpus, minimum_occurrences=minimum)
        return insights, f"Found {len(insights)} recurring pattern(s).", InsightEventType.PATTERNS_DETECTED

    def _identify_habits(self, request: InsightRequest, corpus, by_type):
        reflections = by_type.get(MEMORY_TYPE_REFLECTION, ())
        minimum = request.minimum_occurrences or self.insight_policy.default_habit_minimum_occurrences
        insights = self.engine.identify_habits(reflections, minimum_occurrences=minimum)
        return insights, f"Identified {len(insights)} habit signal(s).", InsightEventType.HABITS_IDENTIFIED

    def _detect_contradictions(self, request: InsightRequest, corpus, by_type):
        preferences = by_type.get(MEMORY_TYPE_PREFERENCE, ())
        comparison = self._comparison_items(by_type)
        insights = self.engine.detect_contradictions(preferences, comparison)
        return insights, f"Detected {len(insights)} possible contradiction(s).", InsightEventType.CONTRADICTIONS_DETECTED

    def _measure_alignment(self, request: InsightRequest, corpus, by_type):
        goals = by_type.get(MEMORY_TYPE_GOAL, ())
        recent_activity = self._recent_activity_items(by_type)
        insights = self.engine.measure_alignment(goals, recent_activity)
        return insights, f"Measured alignment for {len(insights)} goal(s).", InsightEventType.ALIGNMENT_MEASURED

    def _generate_periodic_reflection(self, request: InsightRequest, corpus, by_type):
        reflections = by_type.get(MEMORY_TYPE_REFLECTION, ())
        goals = by_type.get(MEMORY_TYPE_GOAL, ())
        recent_activity = self._recent_activity_items(by_type)
        minimum = request.minimum_occurrences or self.insight_policy.default_pattern_minimum_occurrences
        patterns = self.engine.detect_patterns(corpus, minimum_occurrences=minimum)
        habits = self.engine.identify_habits(
            reflections, minimum_occurrences=self.insight_policy.default_habit_minimum_occurrences
        )
        alignment = self.engine.measure_alignment(goals, recent_activity)
        reflection = self.engine.generate_periodic_reflection(
            period=request.period,
            window_items=corpus,
            pattern_insights=patterns,
            habit_insights=habits,
            alignment_insights=alignment,
        )
        return (
            (reflection,),
            f"Generated a {request.period.value} reflection.",
            InsightEventType.PERIODIC_REFLECTION_GENERATED,
        )

    def _generate_recommendations(self, request: InsightRequest, corpus, by_type):
        preferences = by_type.get(MEMORY_TYPE_PREFERENCE, ())
        reflections = by_type.get(MEMORY_TYPE_REFLECTION, ())
        goals = by_type.get(MEMORY_TYPE_GOAL, ())
        recent_activity = self._recent_activity_items(by_type)
        comparison = self._comparison_items(by_type)
        habits = self.engine.identify_habits(
            reflections, minimum_occurrences=self.insight_policy.default_habit_minimum_occurrences
        )
        contradictions = self.engine.detect_contradictions(preferences, comparison)
        alignment = self.engine.measure_alignment(goals, recent_activity)
        insights = self.engine.generate_recommendations(
            habit_insights=habits, contradiction_insights=contradictions, alignment_insights=alignment
        )
        return insights, f"Generated {len(insights)} recommendation(s).", InsightEventType.RECOMMENDATIONS_GENERATED

    def _update_profile(self, request: InsightRequest, corpus, by_type):
        preferences = by_type.get(MEMORY_TYPE_PREFERENCE, ())
        reflections = by_type.get(MEMORY_TYPE_REFLECTION, ())
        goals = by_type.get(MEMORY_TYPE_GOAL, ())
        recent_activity = self._recent_activity_items(by_type)
        comparison = self._comparison_items(by_type)
        minimum = self.insight_policy.default_pattern_minimum_occurrences
        patterns = self.engine.detect_patterns(corpus, minimum_occurrences=minimum)
        habits = self.engine.identify_habits(
            reflections, minimum_occurrences=self.insight_policy.default_habit_minimum_occurrences
        )
        contradictions = self.engine.detect_contradictions(preferences, comparison)
        alignment = self.engine.measure_alignment(goals, recent_activity)
        profile = self.engine.synthesize_profile(recent_insights=patterns + habits + contradictions + alignment)
        return (profile,), "Updated the long-term personal profile.", InsightEventType.PROFILE_UPDATED

    @staticmethod
    def _recent_activity_items(by_type: dict[str, tuple[ContextItem, ...]]) -> tuple[ContextItem, ...]:
        return by_type.get(MEMORY_TYPE_REFLECTION, ()) + by_type.get(MEMORY_TYPE_PROJECT, ())

    @staticmethod
    def _comparison_items(by_type: dict[str, tuple[ContextItem, ...]]) -> tuple[ContextItem, ...]:
        return (
            by_type.get(MEMORY_TYPE_GOAL, ())
            + by_type.get(MEMORY_TYPE_PROJECT, ())
            + by_type.get(MEMORY_TYPE_REFLECTION, ())
        )

    @staticmethod
    def _extract_request(context: AgentContext) -> InsightRequest:
        extra = context.agent_metadata.extra
        raw = extra.get("insight_request")
        if isinstance(raw, InsightRequest):
            return raw
        operation_raw = extra.get("operation", InsightOperation.RECALL_INSIGHTS.value)
        period_raw = extra.get("period", InsightPeriod.WEEKLY.value)
        return InsightRequest(
            operation=InsightOperation(operation_raw),
            query=extra.get("query", ""),
            period=InsightPeriod(period_raw),
            lookback_days=extra.get("lookback_days"),
            minimum_occurrences=extra.get("minimum_occurrences"),
            maximum_memories_analyzed=extra.get("maximum_memories_analyzed"),
        )

    def _emit(self, context: SpecialistContext, event_type: InsightEventType, **data: Any) -> None:
        self.event_publisher.publish(
            InsightEvent(
                event_type=event_type,
                execution_id=context.execution_id,
                correlation_id=context.correlation_id,
                agent_id=self.identity.agent_id,
                data=data,
            )
        )


AgentRegistry.register(_INSIGHT_AGENT_NAME, InsightAgent, overwrite=True)
SpecialistRegistry.register(
    _INSIGHT_AGENT_NAME,
    InsightAgent,
    specialization="insight",
    supported_tasks=_SUPPORTED_TASKS,
    overwrite=True,
)
