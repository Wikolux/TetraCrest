"""Evening reflection flow (P2 §3-§5): establish what actually happened,
ask only what is necessary, never assume a reason.

Mirrors MorningInteractionFlow's own shape and honesty discipline
exactly: free-text parsing is a clearly-labeled heuristic, not real NLU
(no LLM provider is registered anywhere on this platform); the one real
generative step (the closing acknowledgment) reuses RuntimeAdapter/
PromptBuilder, never a hand-rolled string pretending to be a model call.

The interaction is at most two rounds - open() -> submit() -> (only if
genuinely ambiguous) one selective resolve_follow_up() - never an
iterative back-and-forth, matching §3's "do not force a long
questionnaire" and the worked example's own single follow-up shape.
Anything still ambiguous after the one follow-up reconciles to UNKNOWN,
honestly, rather than being interrogated further.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.types import RuntimeRequest, RuntimeResponse
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.context.types import ContextItem, ContextPackage, ContextSection
from app.services.prompt_builder.builder import PromptBuilder
from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.evening import EveningReflection, EveningReflectionRepository
from app.services.personal_os.planning import AdaptivePlanner, PlanRecommendation
from app.services.personal_os.reasoning import Hypothesis, InferredPattern, ObservedFact, UserExplanation
from app.services.personal_os.reconciliation import ReconciliationEvidence, ReconciliationRecord, reconcile_all
from app.services.personal_os.repository import DailyIntentRepository
from app.services.personal_os.shared.types import ReconciliationStatus

_POSITIVE_MARKERS = ("finished", "completed", "done", "shipped", "wrapped up", "got through")
# Deliberately NOT "didn't get to"/"ran out of time" etc. here - those are
# negations, not a stated reason. A stated reason only exists once the
# user actually gives one (in the original text or the follow-up); until
# then the activity is ambiguous, not silently assumed postponed.
_POSTPONED_MARKERS = ("postponed", "pushed", "next time")
_BLOCKED_MARKERS = ("blocked", "stuck", "waiting on", "couldn't proceed")
_CANCELLED_MARKERS = ("cancelled", "canceled", "scrapped", "dropped", "no longer needed", "decided not to")
_SUPERSEDED_MARKERS = ("priorities changed", "something else came up", "instead", "more important")
_NEGATIVE_ONLY_MARKERS = ("didn't", "did not", "couldn't", "could not", "wasn't able", "was not able", "no")
_REST_MARKERS = ("just rested", "took the day off", "rest day", "took it easy")
_CLAUSE_SPLIT_PATTERN = r"[,;.]| but | however | although "


@dataclass(frozen=True)
class EveningPrompt:
    greeting: str
    context_summary: str
    open_question: str


@dataclass(frozen=True)
class ActivityAssessment:
    """One planned activity's status after parsing user text - AMBIGUOUS
    means a reason is still needed before it can be reconciled to
    anything more specific than UNKNOWN."""

    activity: PlannedActivity
    evidence: ReconciliationEvidence | None
    ambiguous: bool


@dataclass(frozen=True)
class EveningSubmitResult:
    needs_follow_up: bool
    follow_up_question: str = ""
    ambiguous_activities: tuple[PlannedActivity, ...] = field(default_factory=tuple)
    # Evidence already resolved for the NON-ambiguous activities from this
    # same submit() call - carried forward into resolve_follow_up() so
    # already-determined outcomes are never lost or re-asked about.
    resolved_evidence_by_description: dict = field(default_factory=dict)
    resolved_accomplishments: tuple[str, ...] = field(default_factory=tuple)
    reflection: EveningReflection | None = None
    reconciliations: tuple[ReconciliationRecord, ...] = field(default_factory=tuple)
    tomorrow_recommendations: tuple[PlanRecommendation, ...] = field(default_factory=tuple)
    acknowledgment: str = ""


def _split_clauses(text: str) -> list[str]:
    import re

    return [clause.strip() for clause in re.split(_CLAUSE_SPLIT_PATTERN, text) if clause.strip()]


def _mentions(clause: str, activity: PlannedActivity) -> bool:
    lowered = clause.lower()
    description_words = [word for word in activity.description.lower().split() if len(word) > 3]
    return any(word in lowered for word in description_words)


def _assess_activity(activity: PlannedActivity, clauses: list[str]) -> ActivityAssessment:
    relevant_clauses = [clause for clause in clauses if _mentions(clause, activity)]
    if not relevant_clauses:
        return ActivityAssessment(activity, evidence=None, ambiguous=True)

    combined = " ".join(relevant_clauses).lower()
    if any(marker in combined for marker in _CANCELLED_MARKERS):
        return ActivityAssessment(activity, ReconciliationEvidence(explicitly_cancelled=True, note=" ".join(relevant_clauses)), ambiguous=False)
    if any(marker in combined for marker in _BLOCKED_MARKERS):
        return ActivityAssessment(activity, ReconciliationEvidence(explicitly_blocked=True, note=" ".join(relevant_clauses)), ambiguous=False)
    if any(marker in combined for marker in _SUPERSEDED_MARKERS):
        return ActivityAssessment(
            activity, ReconciliationEvidence(superseding_priority=" ".join(relevant_clauses)), ambiguous=False
        )
    if any(marker in combined for marker in _POSTPONED_MARKERS):
        return ActivityAssessment(activity, ReconciliationEvidence(explicitly_postponed=True, note=" ".join(relevant_clauses)), ambiguous=False)
    if any(marker in combined for marker in _POSITIVE_MARKERS):
        return ActivityAssessment(activity, ReconciliationEvidence(explicitly_completed=True), ambiguous=False)
    if any(marker in combined for marker in _NEGATIVE_ONLY_MARKERS):
        # Mentioned, clearly not done, but no reason given yet - exactly
        # the case §3's own worked example asks a selective follow-up
        # about, never assumed.
        return ActivityAssessment(activity, evidence=None, ambiguous=True)
    return ActivityAssessment(activity, evidence=None, ambiguous=True)


class EveningReflectionFlow:
    def __init__(
        self,
        daily_intent_repository: DailyIntentRepository,
        evening_repository: EveningReflectionRepository,
        runtime_adapter: RuntimeAdapter | None = None,
        default_provider: ProviderName = ProviderName.OPENAI,
    ) -> None:
        self.daily_intent_repository = daily_intent_repository
        self.evening_repository = evening_repository
        self.runtime_adapter = runtime_adapter or RuntimeAdapter()
        self.default_provider = default_provider
        self.planner = AdaptivePlanner()

    def open(self, *, organization_id: int, user_id: int, today: date) -> EveningPrompt:
        intent = self.daily_intent_repository.get_for_date(organization_id=organization_id, user_id=user_id, intent_date=today)
        if intent is None:
            return EveningPrompt(
                greeting="Good evening.",
                context_summary="No plan was recorded for today.",
                open_question="How did today go?",
            )
        if intent.is_rest_day:
            return EveningPrompt(
                greeting="Good evening.",
                context_summary="Today was set as a rest day.",
                open_question="How did today go?",
            )
        names = ", ".join(activity.description for activity in intent.planned_activities)
        context_summary = f"You planned: {names}." if names else "No specific activities were planned today."
        return EveningPrompt(greeting="Good evening.", context_summary=context_summary, open_question="How did today go?")

    def submit(
        self, *, organization_id: int, user_id: int, conversation_id: int | None, today: date, user_text: str
    ) -> EveningSubmitResult:
        if not user_text:
            raise ValueError("EveningReflectionFlow.submit() requires non-empty user_text")

        intent = self.daily_intent_repository.get_for_date(organization_id=organization_id, user_id=user_id, intent_date=today)

        if intent is not None and intent.is_rest_day:
            evidence_by_description = {a.description: ReconciliationEvidence(explicitly_rested_instead=True) for a in intent.planned_activities}
            return self._finalize(
                organization_id=organization_id,
                user_id=user_id,
                conversation_id=conversation_id,
                today=today,
                intent=intent,
                evidence_by_description=evidence_by_description,
                accomplishments=(),
                narrative_text=user_text,
            )

        lowered = user_text.lower()
        if intent is not None and any(marker in lowered for marker in _REST_MARKERS):
            evidence_by_description = {a.description: ReconciliationEvidence(explicitly_rested_instead=True) for a in intent.planned_activities}
            return self._finalize(
                organization_id=organization_id,
                user_id=user_id,
                conversation_id=conversation_id,
                today=today,
                intent=intent,
                evidence_by_description=evidence_by_description,
                accomplishments=(),
                narrative_text=user_text,
            )

        planned_activities = intent.planned_activities if intent is not None else ()
        clauses = _split_clauses(user_text)
        assessments = [_assess_activity(activity, clauses) for activity in planned_activities]
        ambiguous = tuple(a.activity for a in assessments if a.ambiguous)

        if ambiguous:
            names = ", ".join(a.description for a in ambiguous)
            question = (
                f"You planned to {names}. "
                + ("It sounds like that didn't happen - " if len(ambiguous) == 1 else "It sounds like those didn't happen - ")
                + "was that because priorities changed, you ran out of time, or something else?"
            )
            resolved_evidence = {a.activity.description: a.evidence for a in assessments if a.evidence is not None}
            resolved_accomplishments = tuple(
                a.activity.description for a in assessments if a.evidence is not None and a.evidence.explicitly_completed
            )
            return EveningSubmitResult(
                needs_follow_up=True,
                follow_up_question=question,
                ambiguous_activities=ambiguous,
                resolved_evidence_by_description=resolved_evidence,
                resolved_accomplishments=resolved_accomplishments,
            )

        evidence_by_description = {a.activity.description: a.evidence for a in assessments if a.evidence is not None}
        accomplishments = tuple(
            a.activity.description for a in assessments if a.evidence is not None and a.evidence.explicitly_completed
        )
        return self._finalize(
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
            today=today,
            intent=intent,
            evidence_by_description=evidence_by_description,
            accomplishments=accomplishments,
            narrative_text=user_text,
        )

    def resolve_follow_up(
        self,
        *,
        organization_id: int,
        user_id: int,
        conversation_id: int | None,
        today: date,
        ambiguous_activities: tuple[PlannedActivity, ...],
        follow_up_text: str,
        resolved_evidence_by_description: dict | None = None,
        resolved_accomplishments: tuple[str, ...] = (),
    ) -> EveningSubmitResult:
        """One selective follow-up round only (§3) - whatever this
        doesn't resolve reconciles to UNKNOWN, honestly, rather than
        being asked about again.

        resolved_evidence_by_description/resolved_accomplishments are the
        caller's own prior submit() result's fields - the evidence
        already determined for the day's other, non-ambiguous activities.
        They must be passed back in here, since this call is otherwise
        stateless (matching every other flow/planner on this platform);
        omitting them silently loses those activities' outcomes, so this
        method never re-derives them from scratch."""
        if not follow_up_text:
            raise ValueError("EveningReflectionFlow.resolve_follow_up() requires non-empty follow_up_text")

        intent = self.daily_intent_repository.get_for_date(organization_id=organization_id, user_id=user_id, intent_date=today)
        lowered = follow_up_text.lower()

        if any(marker in lowered for marker in _CANCELLED_MARKERS):
            evidence = ReconciliationEvidence(explicitly_cancelled=True, note=follow_up_text)
        elif any(marker in lowered for marker in _BLOCKED_MARKERS):
            evidence = ReconciliationEvidence(explicitly_blocked=True, note=follow_up_text)
        elif any(marker in lowered for marker in _SUPERSEDED_MARKERS):
            evidence = ReconciliationEvidence(superseding_priority=follow_up_text)
        else:
            # "Ran out of time," "priorities changed" without an explicit
            # supersession, or any other stated reason not matching a
            # sharper category - postponed is the honest default for "I
            # didn't get to it, and here is why," never left UNKNOWN once
            # a real explanation was actually given.
            evidence = ReconciliationEvidence(explicitly_postponed=True, note=follow_up_text)

        evidence_by_description = dict(resolved_evidence_by_description or {})
        for activity in ambiguous_activities:
            evidence_by_description[activity.description] = evidence

        return self._finalize(
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
            today=today,
            intent=intent,
            evidence_by_description=evidence_by_description,
            accomplishments=resolved_accomplishments,
            narrative_text=follow_up_text,
        )

    def _finalize(
        self,
        *,
        organization_id: int,
        user_id: int,
        conversation_id: int | None,
        today: date,
        intent: DailyIntent | None,
        evidence_by_description: dict[str, ReconciliationEvidence],
        accomplishments: tuple[str, ...],
        narrative_text: str,
    ) -> EveningSubmitResult:
        planned_activities = intent.planned_activities if intent is not None else ()
        reconciliations = reconcile_all(planned_activities, evidence_by_description)

        reflection = EveningReflection(
            reflection_date=today,
            accomplishments=accomplishments,
            evidence_by_activity_description=evidence_by_description,
        )
        self.evening_repository.save(
            reflection,
            reconciliations,
            organization_id=organization_id,
            user_id=user_id,
            daily_intent_id=intent.intent_id if intent is not None else None,
        )

        recommendations = self.planner.recommend(intent, reconciliations) if intent is not None else ()
        runtime_response = self._acknowledge(narrative_text, organization_id, conversation_id)
        acknowledgment = (
            runtime_response.conversation_response.text
            if runtime_response.success and runtime_response.conversation_response
            else "Got it - logged today's outcomes."
        )

        return EveningSubmitResult(
            needs_follow_up=False,
            reflection=reflection,
            reconciliations=reconciliations,
            tomorrow_recommendations=recommendations,
            acknowledgment=acknowledgment,
        )

    def _acknowledge(self, user_text: str, organization_id: int, conversation_id: int | None) -> RuntimeResponse:
        """The one real Runtime integration point in this flow - mirrors
        MorningInteractionFlow._acknowledge() exactly."""
        package = ContextPackage(
            sections=[
                ContextSection(
                    resource_type="evening_reflection",
                    items=[ContextItem(resource_type="evening_reflection", resource_id=0, content=user_text, score=1.0, created_at=datetime.now(UTC))],
                )
            ],
            estimated_tokens=0,
            item_count=1,
            truncated=False,
        )
        prompt_package = PromptBuilder().build(
            f"Acknowledge, in one short sentence, that you understood how today went: {user_text}", package
        )
        runtime_request = RuntimeRequest(
            organization_id=organization_id,
            prompt_package=prompt_package,
            provider=self.default_provider,
            conversation_id=conversation_id,
            parent_shared=SharedExecutionContext(organization_id=organization_id),
        )
        return self.runtime_adapter.execute(runtime_request)


def build_reasoning_trace(reconciliations: tuple[ReconciliationRecord, ...]) -> tuple[ObservedFact, ...] | tuple:
    """Turns reconciled outcomes into ObservedFacts - the raw material a
    future pattern-analysis milestone needs (P2 §9), never a pattern
    engine itself. One fact per non-completed activity; genuine pattern/
    hypothesis construction needs evidence across multiple days, which is
    out of this milestone's own scope (§9's "preserve the evidence rather
    than prematurely implementing a complex pattern engine")."""
    facts = []
    for record in reconciliations:
        if record.status == ReconciliationStatus.COMPLETED:
            continue
        statement = f'"{record.activity.description}" reconciled as {record.status.value}'
        if record.evidence.note:
            statement += f" ({record.evidence.note})"
        facts.append(ObservedFact(statement=statement, evidence_ref=record.activity.description))
    return tuple(facts)


def build_user_explanations(reconciliations: tuple[ReconciliationRecord, ...]) -> tuple[UserExplanation, ...]:
    """The evidence.note a user actually gave, kept structurally distinct
    from the ObservedFact it explains (§4) - never merged into one
    string."""
    explanations = []
    for record in reconciliations:
        note = record.evidence.note or record.evidence.superseding_priority
        if note:
            explanations.append(UserExplanation(statement=note, explains_activity=record.activity.description))
    return tuple(explanations)


def build_hypothesis(facts: tuple[ObservedFact, ...], explanations: tuple[UserExplanation, ...]) -> Hypothesis | None:
    """A single day's own reflection rarely has enough evidence for a
    genuine multi-day pattern (InferredPattern requires 2+ facts, by
    design - reasoning.py) - this only constructs a Hypothesis when
    today's own facts already clear that bar, and is honestly None
    otherwise rather than manufacturing a pattern from one data point."""
    if len(facts) < 2:
        return None
    pattern = InferredPattern(
        statement=f"{len(facts)} planned activities were not completed as originally intended today.",
        supporting_facts=facts,
    )
    if explanations:
        statement = "The day was disrupted by external or changing commitments, per the explanations given."
    else:
        statement = "Multiple planned activities went unresolved today; no explanation was given for why."
    return Hypothesis(statement=statement, explains=pattern, informed_by=explanations)
