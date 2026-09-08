"""P7.17: narrow Pydantic request/response models for Personal OS's own
five API endpoints - never a passthrough of the internal dataclasses
themselves (app/services/personal_os/*.py stays the single source of
truth for domain shape; these models mirror it field-for-field so a
route never needs to invent data the domain doesn't have).

Deterministic state and generated narration are kept as separate fields
throughout (never merged into one prose blob) - PriorityEntry.narrative,
MorningResponse.acknowledgment, EveningSubmitResult.acknowledgment are
each their own string field alongside the structured facts they narrate,
exactly mirroring how the flows themselves already separate the two.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field


# --- shared small shapes -----------------------------------------------------------------------


class DayModeModel(BaseModel):
    kind: str
    custom_label: str = ""
    stated_by_user: bool = True


class PlannedActivityModel(BaseModel):
    description: str
    focus_area: str = ""
    deadline: date | None = None
    estimated_hours: float | None = None


class IntentFieldModel(BaseModel):
    value: str
    source: str
    confidence: str


class DailyIntentModel(BaseModel):
    intent_id: str
    intent_date: date
    stated_intention: str
    day_type: str
    continuation_of_date: date | None = None
    new_priorities: list[IntentFieldModel] = Field(default_factory=list)
    planned_activities: list[PlannedActivityModel] = Field(default_factory=list)
    is_rest_day: bool = False
    focus_areas: list[str] = Field(default_factory=list)
    known_constraints: list[str] = Field(default_factory=list)
    deadlines: list[str] = Field(default_factory=list)
    scheduling_preferences: list[str] = Field(default_factory=list)
    user_provided_changes: list[str] = Field(default_factory=list)
    supersedes_intent_id: str | None = None
    created_at: datetime
    updated_at: datetime


class PlanRecommendationModel(BaseModel):
    kind: str
    subject: str
    rationale: str


class MorningPromptModel(BaseModel):
    greeting: str
    context_summary: str
    open_question: str
    recommendations: list[PlanRecommendationModel] = Field(default_factory=list)


class LivingActivityModel(BaseModel):
    activity_id: str
    description: str
    status: str
    domain: str | None = None
    deadline: date | None = None
    estimated_hours: float | None = None
    is_unexpected: bool = False
    last_reason: str = ""


class LivingDayModel(BaseModel):
    day_date: date
    available_hours: float
    day_mode: DayModeModel | None = None
    activities: list[LivingActivityModel] = Field(default_factory=list)
    event_count: int


class CandidateItemModel(BaseModel):
    item_id: str
    description: str
    domain: str | None = None
    deadline: date | None = None
    estimated_hours: float | None = None
    is_current_intent: bool = False
    source: str
    source_id: str = ""


class PriorityExplanationModel(BaseModel):
    facts: list[str] = Field(default_factory=list)
    inference: str
    recommendation: str


class PriorityEntryModel(BaseModel):
    item: CandidateItemModel
    total: float
    factor_values: dict[str, float] = Field(default_factory=dict)
    explanation: PriorityExplanationModel
    narrative: str


class PriorityPresentationModel(BaseModel):
    core: list[PriorityEntryModel] = Field(default_factory=list)
    optional: list[PriorityEntryModel] = Field(default_factory=list)
    day_mode: DayModeModel | None = None
    closing_question: str


class DayEventModel(BaseModel):
    event_id: str
    event_type: str
    activity_id: str = ""
    description: str = ""
    domain: str | None = None
    deadline: date | None = None
    estimated_hours: float | None = None
    reason: str = ""
    available_hours: float | None = None
    day_mode: DayModeModel | None = None
    occurred_at: datetime
    sequence: int


class ReconciliationEvidenceModel(BaseModel):
    explicitly_completed: bool = False
    explicitly_postponed: bool = False
    explicitly_cancelled: bool = False
    explicitly_blocked: bool = False
    explicitly_rested_instead: bool = False
    superseding_priority: str = ""
    note: str = ""
    actual_hours: float | None = None


class ReconciliationRecordModel(BaseModel):
    activity: PlannedActivityModel
    status: str
    evidence: ReconciliationEvidenceModel


class EveningReflectionModel(BaseModel):
    reflection_date: date
    accomplishments: list[str] = Field(default_factory=list)
    unexpected_events: list[str] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    worth_remembering: list[str] = Field(default_factory=list)
    preparation_for_tomorrow: list[str] = Field(default_factory=list)
    created_at: datetime


class PersonalStateItemModel(BaseModel):
    memory_type: str
    content: str
    resource_id: int
    created_at: datetime


class PersonalStateModel(BaseModel):
    goals: list[PersonalStateItemModel] = Field(default_factory=list)
    projects: list[PersonalStateItemModel] = Field(default_factory=list)
    reflections: list[PersonalStateItemModel] = Field(default_factory=list)
    decisions: list[PersonalStateItemModel] = Field(default_factory=list)
    discovery_findings: list[PersonalStateItemModel] = Field(default_factory=list)
    delivery_artifacts: list[PersonalStateItemModel] = Field(default_factory=list)
    roadmap_items: list[PersonalStateItemModel] = Field(default_factory=list)
    messages: list[PersonalStateItemModel] = Field(default_factory=list)
    meetings: list[PersonalStateItemModel] = Field(default_factory=list)
    opportunities: list[PersonalStateItemModel] = Field(default_factory=list)
    financial_signals: list[PersonalStateItemModel] = Field(default_factory=list)


class BriefSectionModel(BaseModel):
    domain: str
    status: str
    items: list[str] = Field(default_factory=list)
    note: str = ""


class IntelligenceBriefModel(BaseModel):
    sections: list[BriefSectionModel] = Field(default_factory=list)


# --- GET /personal-os/today ---------------------------------------------------------------------


class TodayResponse(BaseModel):
    date: date
    intent: DailyIntentModel | None = None
    morning_prompt: MorningPromptModel | None = None
    living_day: LivingDayModel
    priorities: PriorityPresentationModel


# --- POST /personal-os/today/intent -------------------------------------------------------------


class IntentSubmitRequest(BaseModel):
    text: str = Field(min_length=1)


class IntentSubmitResponse(BaseModel):
    intent: DailyIntentModel
    acknowledgment: str


# --- POST /personal-os/today/interact -----------------------------------------------------------


class InteractRequest(BaseModel):
    text: str = Field(min_length=1)


class InteractResponse(BaseModel):
    outcome: str
    events: list[DayEventModel] = Field(default_factory=list)
    clarification_question: str = ""
    candidates: list[LivingActivityModel] = Field(default_factory=list)
    message: str = ""


# --- POST /personal-os/today/reflect ------------------------------------------------------------


class ReflectContinuation(BaseModel):
    """Exactly the state EveningReflectionFlow.resolve_follow_up() itself
    requires back from a prior submit() call - opaque from the client's
    own point of view (it never constructs this, only echoes back what
    the API returned), so the client cannot fabricate or manipulate
    Personal OS's own internal reflection lifecycle state directly."""

    ambiguous_activities: list[PlannedActivityModel]
    resolved_evidence_by_description: dict[str, ReconciliationEvidenceModel] = Field(default_factory=dict)
    resolved_accomplishments: list[str] = Field(default_factory=list)


class ReflectRequest(BaseModel):
    text: str = Field(min_length=1)
    continuation: ReflectContinuation | None = None


class ReflectResponse(BaseModel):
    needs_follow_up: bool
    follow_up_question: str = ""
    continuation: ReflectContinuation | None = None
    reflection: EveningReflectionModel | None = None
    reconciliations: list[ReconciliationRecordModel] = Field(default_factory=list)
    tomorrow_recommendations: list[PlanRecommendationModel] = Field(default_factory=list)
    acknowledgment: str = ""


# --- GET /personal-os/brief ----------------------------------------------------------------------


class BriefResponse(BaseModel):
    personal_state: PersonalStateModel
    brief: IntelligenceBriefModel | None = None
    note: str | None = None
