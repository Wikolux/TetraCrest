"""P7.17: Personal OS Core API Surface - the minimal authenticated HTTP
product surface exposing the already-built daily lifecycle (morning
intent -> current-day intelligence -> midday interaction -> evening
reflection -> Personal Intelligence Brief).

Every route here is a thin composition of already-existing, already-
tested Personal OS application flows (MorningInteractionFlow,
EveningReflectionFlow, PriorityIntelligenceFlow, LivingDayFlow,
PersonalStateReader, IntelligenceBriefBuilder) - no ranking, replanning,
interaction interpretation, reflection logic, or narration is
reimplemented here. organization_id/user_id always come from the
authenticated request context (get_current_db_user/
get_current_organization_id), never from a request body; "today" always
comes from resolve_personal_os_today() (server-side, UTC-calendar-date),
never from a client-supplied date.

No Pattern/Experiment/Adaptation decision endpoint, no Mission/Life-
Domain CRUD, no external tool, and no generic chat endpoint exist here -
all explicitly out of this milestone's scope (P7.17 Phase 0 audit, §25-30).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_db_user, get_current_organization_id
from app.models.user import User
from app.schemas.personal_os import (
    BriefResponse,
    BriefSectionModel,
    CandidateItemModel,
    DailyIntentModel,
    DayEventModel,
    DayModeModel,
    EveningReflectionModel,
    InteractRequest,
    InteractResponse,
    IntelligenceBriefModel,
    IntentFieldModel,
    IntentSubmitRequest,
    IntentSubmitResponse,
    LivingActivityModel,
    LivingDayModel,
    MorningPromptModel,
    PersonalStateItemModel,
    PersonalStateModel,
    PlannedActivityModel,
    PlanRecommendationModel,
    PriorityEntryModel,
    PriorityExplanationModel,
    PriorityPresentationModel,
    ReconciliationEvidenceModel,
    ReconciliationRecordModel,
    ReflectContinuation,
    ReflectRequest,
    ReflectResponse,
    TodayResponse,
)
from app.services.personal_os.brief import BriefSection, IntelligenceBrief, IntelligenceBriefBuilder
from app.services.personal_os.current_day import resolve_personal_os_today
from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.day_mode import DayMode
from app.services.personal_os.evening import EveningReflection
from app.services.personal_os.evening_flow import EveningReflectionFlow
from app.services.personal_os.living_day import DayEvent, LivingActivity, LivingDayState
from app.services.personal_os.living_day_flow import LivingDayFlow
from app.services.personal_os.morning_flow import MorningInteractionFlow, MorningPrompt
from app.services.personal_os.personal_state import PersonalState, PersonalStateItem, PersonalStateReader
from app.services.personal_os.planning import PlanRecommendation
from app.services.personal_os.priority import CandidateItem, PriorityExplanation
from app.services.personal_os.priority_flow import PriorityEntry, PriorityIntelligenceFlow, PriorityPresentation
from app.services.personal_os.reconciliation import ReconciliationEvidence, ReconciliationRecord
from app.services.personal_os.sql_repository import (
    SqlAdaptationRepository,
    SqlDailyIntentRepository,
    SqlDayEventRepository,
    SqlEveningReflectionRepository,
    SqlExperimentRepository,
    SqlMissionRepository,
    SqlPatternRepository,
)
from database import get_db

router = APIRouter(prefix="/personal-os", tags=["personal-os"])


# --- flow construction (Sql*-backed repositories only - never in-memory in production routes) --


def _build_priority_flow(db: Session) -> PriorityIntelligenceFlow:
    return PriorityIntelligenceFlow(
        intent_repository=SqlDailyIntentRepository(db),
        mission_repository=SqlMissionRepository(db),
        pattern_repository=SqlPatternRepository(db),
        experiment_repository=SqlExperimentRepository(db),
        adaptation_repository=SqlAdaptationRepository(db),
    )


def _build_living_day_flow(db: Session) -> LivingDayFlow:
    return LivingDayFlow(
        intent_repository=SqlDailyIntentRepository(db),
        event_repository=SqlDayEventRepository(db),
        priority_flow=_build_priority_flow(db),
    )


def _build_morning_flow(db: Session) -> MorningInteractionFlow:
    return MorningInteractionFlow(repository=SqlDailyIntentRepository(db), evening_repository=SqlEveningReflectionRepository(db))


def _build_evening_flow(db: Session) -> EveningReflectionFlow:
    return EveningReflectionFlow(daily_intent_repository=SqlDailyIntentRepository(db), evening_repository=SqlEveningReflectionRepository(db))


# --- domain -> API model conversions (deterministic state kept separate from narration) --------


def _day_mode_model(day_mode: DayMode | None) -> DayModeModel | None:
    if day_mode is None:
        return None
    return DayModeModel(kind=day_mode.kind.value, custom_label=day_mode.custom_label, stated_by_user=day_mode.stated_by_user)


def _activity_model(activity: PlannedActivity) -> PlannedActivityModel:
    return PlannedActivityModel(
        description=activity.description, focus_area=activity.focus_area, deadline=activity.deadline, estimated_hours=activity.estimated_hours
    )


def _intent_model(intent: DailyIntent) -> DailyIntentModel:
    return DailyIntentModel(
        intent_id=intent.intent_id,
        intent_date=intent.intent_date,
        stated_intention=intent.stated_intention,
        day_type=intent.day_type.value,
        continuation_of_date=intent.continuation_of_date,
        new_priorities=[IntentFieldModel(value=f.value, source=f.source.value, confidence=f.confidence.value) for f in intent.new_priorities],
        planned_activities=[_activity_model(a) for a in intent.planned_activities],
        is_rest_day=intent.is_rest_day,
        focus_areas=list(intent.focus_areas),
        known_constraints=list(intent.known_constraints),
        deadlines=list(intent.deadlines),
        scheduling_preferences=list(intent.scheduling_preferences),
        user_provided_changes=list(intent.user_provided_changes),
        supersedes_intent_id=intent.supersedes_intent_id,
        created_at=intent.created_at,
        updated_at=intent.updated_at,
    )


def _recommendation_model(recommendation: PlanRecommendation) -> PlanRecommendationModel:
    return PlanRecommendationModel(kind=recommendation.kind.value, subject=recommendation.subject, rationale=recommendation.rationale)


def _morning_prompt_model(prompt: MorningPrompt) -> MorningPromptModel:
    return MorningPromptModel(
        greeting=prompt.greeting,
        context_summary=prompt.context_summary,
        open_question=prompt.open_question,
        recommendations=[_recommendation_model(r) for r in prompt.recommendations],
    )


def _living_activity_model(activity: LivingActivity) -> LivingActivityModel:
    return LivingActivityModel(
        activity_id=activity.activity_id,
        description=activity.description,
        status=activity.status.value,
        domain=activity.domain.value if activity.domain else None,
        deadline=activity.deadline,
        estimated_hours=activity.estimated_hours,
        is_unexpected=activity.is_unexpected,
        last_reason=activity.last_reason,
    )


def _living_day_model(state: LivingDayState) -> LivingDayModel:
    return LivingDayModel(
        day_date=state.day_date,
        available_hours=state.available_hours,
        day_mode=_day_mode_model(state.day_mode),
        activities=[_living_activity_model(a) for a in state.activities],
        event_count=len(state.events),
    )


def _candidate_item_model(item: CandidateItem) -> CandidateItemModel:
    return CandidateItemModel(
        item_id=item.item_id,
        description=item.description,
        domain=item.domain.value if item.domain else None,
        deadline=item.deadline,
        estimated_hours=item.estimated_hours,
        is_current_intent=item.is_current_intent,
        source=item.source,
        source_id=item.source_id,
    )


def _explanation_model(explanation: PriorityExplanation) -> PriorityExplanationModel:
    return PriorityExplanationModel(facts=list(explanation.facts), inference=explanation.inference, recommendation=explanation.recommendation)


def _entry_model(entry: PriorityEntry) -> PriorityEntryModel:
    return PriorityEntryModel(
        item=_candidate_item_model(entry.score.item),
        total=entry.score.total,
        factor_values={factor.value: value for factor, value in entry.score.factor_values.items()},
        explanation=_explanation_model(entry.explanation),
        narrative=entry.narrative,
    )


def _presentation_model(presentation: PriorityPresentation) -> PriorityPresentationModel:
    return PriorityPresentationModel(
        core=[_entry_model(e) for e in presentation.core],
        optional=[_entry_model(e) for e in presentation.optional],
        day_mode=_day_mode_model(presentation.day_mode),
        closing_question=presentation.closing_question,
    )


def _event_model(event: DayEvent) -> DayEventModel:
    return DayEventModel(
        event_id=event.event_id,
        event_type=event.event_type.value,
        activity_id=event.activity_id,
        description=event.description,
        domain=event.domain.value if event.domain else None,
        deadline=event.deadline,
        estimated_hours=event.estimated_hours,
        reason=event.reason,
        available_hours=event.available_hours,
        day_mode=_day_mode_model(event.day_mode),
        occurred_at=event.occurred_at,
        sequence=event.sequence,
    )


def _evidence_model(evidence: ReconciliationEvidence) -> ReconciliationEvidenceModel:
    return ReconciliationEvidenceModel(
        explicitly_completed=evidence.explicitly_completed,
        explicitly_postponed=evidence.explicitly_postponed,
        explicitly_cancelled=evidence.explicitly_cancelled,
        explicitly_blocked=evidence.explicitly_blocked,
        explicitly_rested_instead=evidence.explicitly_rested_instead,
        superseding_priority=evidence.superseding_priority,
        note=evidence.note,
        actual_hours=evidence.actual_hours,
    )


def _reconciliation_model(record: ReconciliationRecord) -> ReconciliationRecordModel:
    return ReconciliationRecordModel(activity=_activity_model(record.activity), status=record.status.value, evidence=_evidence_model(record.evidence))


def _reflection_model(reflection: EveningReflection) -> EveningReflectionModel:
    return EveningReflectionModel(
        reflection_date=reflection.reflection_date,
        accomplishments=list(reflection.accomplishments),
        unexpected_events=list(reflection.unexpected_events),
        lessons=list(reflection.lessons),
        decisions=list(reflection.decisions),
        worth_remembering=list(reflection.worth_remembering),
        preparation_for_tomorrow=list(reflection.preparation_for_tomorrow),
        created_at=reflection.created_at,
    )


def _personal_state_item_model(item: PersonalStateItem) -> PersonalStateItemModel:
    return PersonalStateItemModel(memory_type=item.memory_type, content=item.content, resource_id=item.resource_id, created_at=item.created_at)


def _personal_state_model(state: PersonalState) -> PersonalStateModel:
    return PersonalStateModel(
        goals=[_personal_state_item_model(i) for i in state.goals],
        projects=[_personal_state_item_model(i) for i in state.projects],
        reflections=[_personal_state_item_model(i) for i in state.reflections],
        decisions=[_personal_state_item_model(i) for i in state.decisions],
        discovery_findings=[_personal_state_item_model(i) for i in state.discovery_findings],
        delivery_artifacts=[_personal_state_item_model(i) for i in state.delivery_artifacts],
        roadmap_items=[_personal_state_item_model(i) for i in state.roadmap_items],
        messages=[_personal_state_item_model(i) for i in state.messages],
        meetings=[_personal_state_item_model(i) for i in state.meetings],
        opportunities=[_personal_state_item_model(i) for i in state.opportunities],
        financial_signals=[_personal_state_item_model(i) for i in state.financial_signals],
    )


def _brief_section_model(section: BriefSection) -> BriefSectionModel:
    return BriefSectionModel(domain=section.domain.value, status=section.status.value, items=list(section.items), note=section.note)


def _brief_model(brief: IntelligenceBrief) -> IntelligenceBriefModel:
    return IntelligenceBriefModel(sections=[_brief_section_model(s) for s in brief.sections])


# --- request -> domain conversions (for the reflection continuation echo) ----------------------


def _planned_activity_from_model(model: PlannedActivityModel) -> PlannedActivity:
    return PlannedActivity(description=model.description, focus_area=model.focus_area, deadline=model.deadline, estimated_hours=model.estimated_hours)


def _evidence_from_model(model: ReconciliationEvidenceModel) -> ReconciliationEvidence:
    return ReconciliationEvidence(
        explicitly_completed=model.explicitly_completed,
        explicitly_postponed=model.explicitly_postponed,
        explicitly_cancelled=model.explicitly_cancelled,
        explicitly_blocked=model.explicitly_blocked,
        explicitly_rested_instead=model.explicitly_rested_instead,
        superseding_priority=model.superseding_priority,
        note=model.note,
        actual_hours=model.actual_hours,
    )


def _continuation_from_result(needs_follow_up: bool, ambiguous_activities, resolved_evidence_by_description, resolved_accomplishments) -> ReflectContinuation | None:
    if not needs_follow_up:
        return None
    return ReflectContinuation(
        ambiguous_activities=[_activity_model(a) for a in ambiguous_activities],
        resolved_evidence_by_description={k: _evidence_model(v) for k, v in resolved_evidence_by_description.items()},
        resolved_accomplishments=list(resolved_accomplishments),
    )


# --- routes --------------------------------------------------------------------------------------


@router.get("/today", response_model=TodayResponse)
def get_today(
    user: User = Depends(get_current_db_user),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> TodayResponse:
    """Read-only, bootstrap-safe current-day view - a brand-new account
    with no DailyIntent/DayEvents returns a valid, honest empty shape,
    never an error and never fabricated content."""
    today = resolve_personal_os_today()
    intent_repository = SqlDailyIntentRepository(db)
    intent = intent_repository.get_for_date(organization_id=organization_id, user_id=user.id, intent_date=today)

    living_day_flow = _build_living_day_flow(db)
    state = living_day_flow.get_state(organization_id=organization_id, user_id=user.id, today=today)
    presentation = living_day_flow.present_replan(organization_id=organization_id, user_id=user.id, today=today)

    morning_prompt = None
    if intent is None:
        morning_prompt = _morning_prompt_model(_build_morning_flow(db).open(organization_id=organization_id, user_id=user.id, today=today))

    return TodayResponse(
        date=today,
        intent=_intent_model(intent) if intent is not None else None,
        morning_prompt=morning_prompt,
        living_day=_living_day_model(state),
        priorities=_presentation_model(presentation),
    )


@router.post("/today/intent", response_model=IntentSubmitResponse)
def submit_intent(
    payload: IntentSubmitRequest,
    user: User = Depends(get_current_db_user),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> IntentSubmitResponse:
    today = resolve_personal_os_today()
    flow = _build_morning_flow(db)
    result = flow.submit(organization_id=organization_id, user_id=user.id, conversation_id=None, today=today, user_text=payload.text)
    return IntentSubmitResponse(intent=_intent_model(result.intent), acknowledgment=result.acknowledgment)


@router.post("/today/interact", response_model=InteractResponse)
def interact(
    payload: InteractRequest,
    user: User = Depends(get_current_db_user),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> InteractResponse:
    """Preserves P6.4 semantics exactly - the heuristic interpreter
    decides the outcome; this route never reinterprets the statement and
    never asks a model to classify it."""
    today = resolve_personal_os_today()
    flow = _build_living_day_flow(db)
    result = flow.apply_statement(organization_id=organization_id, user_id=user.id, today=today, user_text=payload.text)
    return InteractResponse(
        outcome=result.outcome.value,
        events=[_event_model(e) for e in result.events],
        clarification_question=result.clarification_question,
        candidates=[_living_activity_model(c) for c in result.candidates],
        message=result.message,
    )


@router.post("/today/reflect", response_model=ReflectResponse)
def reflect(
    payload: ReflectRequest,
    user: User = Depends(get_current_db_user),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> ReflectResponse:
    """Preserves EveningReflectionFlow's own bounded, at-most-two-round
    shape - `continuation` (present only on a genuine follow-up call,
    and only ever containing exactly what a prior submit() response
    itself returned) is the sole discriminator between an initial
    submission and a follow-up resolution; the client can never
    construct one from scratch or otherwise manipulate the reflection
    lifecycle directly."""
    today = resolve_personal_os_today()
    flow = _build_evening_flow(db)

    if payload.continuation is None:
        result = flow.submit(organization_id=organization_id, user_id=user.id, conversation_id=None, today=today, user_text=payload.text)
    else:
        ambiguous_activities = tuple(_planned_activity_from_model(a) for a in payload.continuation.ambiguous_activities)
        resolved_evidence_by_description = {
            description: _evidence_from_model(evidence) for description, evidence in payload.continuation.resolved_evidence_by_description.items()
        }
        result = flow.resolve_follow_up(
            organization_id=organization_id,
            user_id=user.id,
            conversation_id=None,
            today=today,
            ambiguous_activities=ambiguous_activities,
            follow_up_text=payload.text,
            resolved_evidence_by_description=resolved_evidence_by_description,
            resolved_accomplishments=tuple(payload.continuation.resolved_accomplishments),
        )

    return ReflectResponse(
        needs_follow_up=result.needs_follow_up,
        follow_up_question=result.follow_up_question,
        continuation=_continuation_from_result(
            result.needs_follow_up, result.ambiguous_activities, result.resolved_evidence_by_description, result.resolved_accomplishments
        ),
        reflection=_reflection_model(result.reflection) if result.reflection is not None else None,
        reconciliations=[_reconciliation_model(r) for r in result.reconciliations],
        tomorrow_recommendations=[_recommendation_model(r) for r in result.tomorrow_recommendations],
        acknowledgment=result.acknowledgment,
    )


@router.get("/brief", response_model=BriefResponse)
def get_brief(
    user: User = Depends(get_current_db_user),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> BriefResponse:
    """'What does Personal OS currently understand about me?' - never
    another /today. Reports the existing, honest NOT_YET_CONNECTED
    sections exactly as they exist; never fabricates a connected domain,
    and never fabricates a DailyIntent merely to satisfy
    IntelligenceBriefBuilder.build()'s own signature when none exists
    yet for today."""
    today = resolve_personal_os_today()
    state = PersonalStateReader().read(organization_id=organization_id)
    intent = SqlDailyIntentRepository(db).get_for_date(organization_id=organization_id, user_id=user.id, intent_date=today)

    if intent is None:
        return BriefResponse(
            personal_state=_personal_state_model(state),
            brief=None,
            note="No daily intent recorded yet for today - submit one via POST /personal-os/today/intent to see today's priorities in context.",
        )

    brief = IntelligenceBriefBuilder().build(state, intent)
    return BriefResponse(personal_state=_personal_state_model(state), brief=_brief_model(brief), note=None)
