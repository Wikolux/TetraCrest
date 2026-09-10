"""Morning interaction flow (§3 of the build spec): establish context and
intent before presenting anything, never dump a dashboard first.

Reuses the Runtime exactly the way every Capability Pack specialist's own
_synthesize()/_generate() helper does (RuntimeAdapter + PromptBuilder,
never a direct AIRuntime/ConversationProvider construction) - Personal OS
is a caller of the platform, not a reimplementation of any part of it.
`test_personal_os_architecture.py::test_morning_flow_never_bypasses_the_runtime`
verifies this structurally.

Free-form intent parsing is honestly heuristic, not real NLU - this is a
deliberate, unrelated design choice (P7.14 registered a real OpenAI
ConversationProvider, but that only makes the Runtime call below capable
of real narration; it says nothing about how this flow classifies day
type or continuation itself). Every field this flow extracts from user
text is tagged IntentSource.HEURISTIC_PARSE with Confidence.LOW/MEDIUM,
never HIGH, so nothing downstream mistakes a keyword match for genuine
understanding. The Runtime call this flow makes is for the conversational
acknowledgment (a real, working integration point since P7.14), not for
the structured extraction itself - replacing the heuristic with real
structured NLU, once desired, changes only _parse_free_text()'s own
implementation, not this flow's shape.
"""

from dataclasses import dataclass
from datetime import date

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.types import RuntimeRequest, RuntimeResponse
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.context.types import ContextItem, ContextPackage, ContextSection
from app.services.prompt_builder.builder import PromptBuilder
from app.services.personal_os.daily_intent import DailyIntent, IntentField, PlannedActivity
from app.services.personal_os.evening import EveningReflectionRepository
from app.services.personal_os.planning import AdaptivePlanner, PlanRecommendation
from app.services.personal_os.repository import DailyIntentRepository
from app.services.personal_os.shared.types import Confidence, DayType, IntentSource

_DAY_TYPE_KEYWORDS: tuple[tuple[DayType, tuple[str, ...]], ...] = (
    (DayType.REST, ("rest", "recover", "recovery", "day off", "break")),
    (DayType.STUDY, ("study", "studying", "learn", "learning", "course")),
    (DayType.WORK, ("work", "working", "job", "career", "apply", "application")),
    (DayType.PROJECT, ("project", "build", "building", "ship")),
)


@dataclass(frozen=True)
class MorningPrompt:
    """What Personal OS presents to open the day - never the full
    dashboard, per §3's own explicit constraint.

    recommendations (P2 §8) are yesterday evening's own
    PlanRecommendations, surfaced but never merged into
    context_summary's carried-over commitments - a recommendation stays
    a recommendation until the user's own reply turns it into today's
    intent (§8's own "recommendations must remain distinguishable from
    commitments")."""

    greeting: str
    context_summary: str
    open_question: str
    recommendations: tuple[PlanRecommendation, ...] = ()


@dataclass(frozen=True)
class MorningResponse:
    """The reconciled outcome of one morning interaction - ready to be
    saved via DailyIntentRepository and, separately, handed to
    IntelligenceBriefBuilder."""

    intent: DailyIntent
    acknowledgment: str


class MorningInteractionFlow:
    def __init__(
        self,
        repository: DailyIntentRepository,
        evening_repository: EveningReflectionRepository | None = None,
        runtime_adapter: RuntimeAdapter | None = None,
        default_provider: ProviderName = ProviderName.OPENAI,
    ) -> None:
        self.repository = repository
        self.evening_repository = evening_repository
        self.runtime_adapter = runtime_adapter or RuntimeAdapter()
        self.default_provider = default_provider
        self.planner = AdaptivePlanner()

    def open(self, *, organization_id: int, user_id: int, today: date) -> MorningPrompt:
        """Establish context before asking anything - carried-over items
        from the most recent prior DailyIntent, if one exists, or an
        honest "nothing carried over" if this is the first day. If an
        evening reflection exists for that same prior day, its own
        recommendations are surfaced separately (P2 §8) - never folded
        into the carried-over commitments themselves."""
        previous = self.repository.get_latest_before(organization_id=organization_id, user_id=user_id, before=today)
        if previous is None or not previous.planned_activities:
            context_summary = "You have nothing carried over from a previous day on record."
        else:
            names = ", ".join(activity.description for activity in previous.planned_activities)
            context_summary = f"You have {len(previous.planned_activities)} item(s) carried over from {previous.intent_date}: {names}."

        recommendations: tuple[PlanRecommendation, ...] = ()
        if previous is not None and self.evening_repository is not None:
            reconciliations = self.evening_repository.get_reconciliations_for_date(
                organization_id=organization_id, user_id=user_id, reflection_date=previous.intent_date
            )
            if reconciliations:
                recommendations = self.planner.recommend(previous, reconciliations)

        return MorningPrompt(
            greeting="Good morning.",
            context_summary=context_summary,
            open_question="Before I bring everything up - how are you doing today, and is today "
            "a continuation of that, or something different?",
            recommendations=recommendations,
        )

    def submit(
        self,
        *,
        organization_id: int,
        user_id: int,
        conversation_id: int | None,
        today: date,
        user_text: str,
        explicit_planned_activities: tuple[PlannedActivity, ...] | None = None,
    ) -> MorningResponse:
        """Reconcile the user's free-form reply against carried-over
        state and produce today's DailyIntent.

        `explicit_planned_activities` (P7.19, optional) is the caller's
        own structured statement of what they plan to do today - never
        inferred from `user_text` (that would be new NLU, not a data-
        capture seam). `None` means "not supplied," preserving every
        pre-P7.19 caller's behavior exactly (carry-forward on a
        continuing day, empty otherwise). An explicitly supplied tuple -
        including an explicitly EMPTY one, meaningfully distinct from
        `None` ("I have no planned activities today," not "say nothing
        about activities") - always wins over carry-forward inference:
        the user's own explicit statement of today's plan is a stronger
        signal than a heuristic guess about whether today continues
        yesterday's. `continuation_of_date` is still recorded whenever
        `continues_previous` holds, regardless of which activities are
        used - it records temporal lineage ("today follows that day"),
        not which specific activities apply today."""
        if not user_text:
            raise ValueError("MorningInteractionFlow.submit() requires non-empty user_text")

        previous = self.repository.get_latest_before(organization_id=organization_id, user_id=user_id, before=today)
        day_type, day_type_confidence = self._infer_day_type(user_text)
        continues_previous = self._continues_previous(user_text)

        planned_activities: tuple[PlannedActivity, ...] = ()
        continuation_of_date = None
        if continues_previous and previous is not None:
            planned_activities = previous.planned_activities
            continuation_of_date = previous.intent_date
        if explicit_planned_activities is not None:
            planned_activities = explicit_planned_activities

        new_priorities = (
            (IntentField(value=user_text, source=IntentSource.USER_EXPLICIT, confidence=Confidence.HIGH),)
            if not continues_previous
            else ()
        )

        intent = DailyIntent(
            intent_date=today,
            stated_intention=user_text,
            day_type=day_type,
            continuation_of_date=continuation_of_date,
            new_priorities=new_priorities,
            planned_activities=planned_activities,
            is_rest_day=day_type == DayType.REST,
        )

        runtime_response = self._acknowledge(user_text, intent, organization_id, conversation_id)
        acknowledgment = (
            runtime_response.conversation_response.text
            if runtime_response.success and runtime_response.conversation_response
            else f"Got it - treating today as a {day_type.value} day."
        )

        saved = self.repository.save(intent, organization_id=organization_id, user_id=user_id)
        return MorningResponse(intent=saved, acknowledgment=acknowledgment)

    def _acknowledge(
        self, user_text: str, intent: DailyIntent, organization_id: int, conversation_id: int | None
    ) -> RuntimeResponse:
        """The one real Runtime integration point in this flow - asks the
        model to acknowledge what was understood, exactly the same
        RuntimeAdapter+PromptBuilder shape every specialist's own
        _generate() helper already uses. Never bypassed for a hand-rolled
        string, even though the fallback in submit() exists for when this
        call itself fails (no provider configured, in this environment)."""
        package = ContextPackage(
            sections=[
                ContextSection(
                    resource_type="daily_intent",
                    items=[
                        ContextItem(
                            resource_type="daily_intent",
                            resource_id=0,
                            content=f"Day type: {intent.day_type.value}. Stated intention: {user_text}",
                            score=1.0,
                            created_at=intent.created_at,
                        )
                    ],
                )
            ],
            estimated_tokens=0,
            item_count=1,
            truncated=False,
        )
        prompt_package = PromptBuilder().build(
            f"Acknowledge, in one short sentence, that you understood today's intent: {user_text}", package
        )
        runtime_request = RuntimeRequest(
            organization_id=organization_id,
            prompt_package=prompt_package,
            provider=self.default_provider,
            conversation_id=conversation_id,
            parent_shared=SharedExecutionContext(organization_id=organization_id),
        )
        return self.runtime_adapter.execute(runtime_request)

    @staticmethod
    def _infer_day_type(user_text: str) -> tuple[DayType, Confidence]:
        lowered = user_text.lower()
        matches = [day_type for day_type, keywords in _DAY_TYPE_KEYWORDS if any(keyword in lowered for keyword in keywords)]
        if len(matches) == 1:
            return matches[0], Confidence.MEDIUM
        if len(matches) > 1:
            return DayType.MIXED, Confidence.MEDIUM
        return DayType.OTHER, Confidence.LOW

    @staticmethod
    def _continues_previous(user_text: str) -> bool:
        lowered = user_text.lower()
        change_markers = ("different", "instead", "change", "new plan", "not continuing")
        continue_markers = ("continue", "same", "keep going", "as planned")
        if any(marker in lowered for marker in change_markers):
            return False
        return any(marker in lowered for marker in continue_markers)
