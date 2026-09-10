"""P7.18: narrow Pydantic request/response models for Personal OS's
governance surface (Pattern/Experiment/Adaptation decisions) - a sibling
of app/schemas/personal_os.py rather than an addition to it, since this
covers a distinct product surface (already-pending human decisions) with
its own, larger request/response family.

Structured evidence and generated narration are kept as separate fields
throughout, never merged (§12 of the P7.18 brief): `evidence`/
`recommendation`/`comparison_outcome` are facts or an already-computed,
deterministic classification; `narrative`/`review_narrative` are the one
generative rephrasing each flow already produces. Neither list/detail
model lets narration stand in for the structured fields it explains.
"""

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class PatternAction(str, Enum):
    CONFIRM = "confirm"
    REJECT = "reject"
    CORRECT = "correct"
    DEFER = "defer"


class AdaptationAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ADOPT = "adopt"
    ROLLBACK = "rollback"


class ExperimentAction(str, Enum):
    """Both decision stages (§17) share one action vocabulary with no
    overlapping values - which subset is actually valid right now is
    determined server-side from the experiment's CURRENT status, never
    trusted from the client, so a stage/status mismatch (e.g.
    `action=approve` on an already-REVIEWED experiment) is a 409 the
    route itself raises, not something this enum could ever detect out
    of context."""

    APPROVE = "approve"
    REJECT = "reject"
    KEEP = "keep"
    MODIFY = "modify"
    STOP = "stop"
    CONTINUE = "continue"
    DEFER = "defer"


# --- GET /personal-os/decisions -----------------------------------------------------------------


class DecisionListItem(BaseModel):
    decision_type: str
    entity_type: Literal["pattern", "experiment", "adaptation"]
    entity_id: str
    current_status: str
    title: str
    summary: str
    evidence: list[str] = Field(default_factory=list)
    confidence: str | None = None
    recommendation: str | None = None
    narrative: str | None = None
    allowed_actions: list[str] = Field(default_factory=list)
    decision_required: bool = True
    created_at: datetime
    updated_at: datetime


class DecisionListResponse(BaseModel):
    items: list[DecisionListItem] = Field(default_factory=list)


# --- GET /personal-os/decisions/{entity_type}/{entity_id} ---------------------------------------


class PatternDecisionDetail(BaseModel):
    entity_type: Literal["pattern"] = "pattern"
    entity_id: str
    pattern_type: str
    pattern_statement: str
    evidence: list[str] = Field(default_factory=list)
    confidence: str
    hypotheses: list[str] = Field(default_factory=list)
    user_interpretation: str = ""
    recommendation: str | None = None
    status: str
    allowed_actions: list[str] = Field(default_factory=list)
    decision_required: bool
    created_at: datetime
    updated_at: datetime


class ExperimentDecisionDetail(BaseModel):
    entity_type: Literal["experiment"] = "experiment"
    entity_id: str
    hypothesis_statement: str
    adjustment: str
    measurement_plan: str
    status: str
    comparison_outcome: str | None = None
    comparison_confidence: str | None = None
    observation_statement: str | None = None
    review_narrative: str = ""
    allowed_actions: list[str] = Field(default_factory=list)
    decision_required: bool
    created_at: datetime
    updated_at: datetime


class AdaptationDecisionDetail(BaseModel):
    entity_type: Literal["adaptation"] = "adaptation"
    entity_id: str
    target_scope: str
    target_id: str
    expected_outcome: str
    confidence: str
    status: str
    effect_kind: str | None = None
    effect_direction: str | None = None
    is_rollback_candidate: bool = False
    rollback_recommendation: str | None = None
    allowed_actions: list[str] = Field(default_factory=list)
    decision_required: bool
    created_at: datetime
    updated_at: datetime


DecisionDetail = Annotated[
    Union[PatternDecisionDetail, ExperimentDecisionDetail, AdaptationDecisionDetail],
    Field(discriminator="entity_type"),
]


# --- POST /personal-os/patterns/{pattern_id}/respond ---------------------------------------------


class PatternActionRequest(BaseModel):
    """`action` membership is validated by the PatternAction enum type
    itself (a clean, JSON-safe 422 on an unknown value); the conditional
    "correction_text required when action is 'correct'" rule depends on
    another field's value, so it cannot be expressed as a plain field
    constraint - see personal_os_decisions.py's own route-layer check
    (a `model_validator` raising ValueError here would hit a pre-existing
    gap in main.py's shared validation_exception_handler, which passes
    exc.errors() straight to JSONResponse without jsonable_encoder;
    Pydantic v2 embeds the raw exception object in that error's own
    `ctx.error`, which is not JSON-serializable. Not fixed here - main.py
    is shared, frozen-by-convention code well outside this milestone's
    scope; worked around by keeping this specific check in the route,
    where HTTPException's own, already-safe serialization path applies)."""

    action: PatternAction
    correction_text: str = ""


# --- POST /personal-os/experiments/{experiment_id}/respond -----------------------------------


class ExperimentActionRequest(BaseModel):
    """See PatternActionRequest's own docstring for why the conditional
    "modification_notes required for modify" / "extended_review_date
    required for continue" rules are validated in the route, not here."""

    action: ExperimentAction
    reason: str = ""
    modification_notes: str = ""
    extended_review_date: date | None = None


# --- POST /personal-os/adaptations/{adaptation_id}/respond -----------------------------------


class AdaptationActionRequest(BaseModel):
    """See PatternActionRequest's own docstring for why the conditional
    "reason required for reject/rollback" rule is validated in the
    route, not here."""

    action: AdaptationAction
    reason: str = ""
