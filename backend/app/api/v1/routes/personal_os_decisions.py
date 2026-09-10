"""P7.18: Personal Learning Governance Surface - lets one authenticated
Personal OS user see already-pending Pattern/Experiment/Adaptation
decisions and make them, through the exact same authoritative flow
methods (PatternDetectionFlow.respond(), ExperimentFlow.approve()/
reject()/decide(), AdaptationFlow.approve()/reject()/adopt()/rollback())
those flows already define - no new lifecycle rule, no status patching,
no second workflow engine.

GET /decisions is strictly read-only: it aggregates entities already in
a decision-requiring state by filtering each repository's own
list_active() read, and never calls a mutating method (surface_next(),
list_ready_for_review(), review(), begin_evaluation()) to manufacture
one. See app/services/personal_os/decisions.py for the pure allowed-
action/rollback-candidate derivation this route composes but never
duplicates.

Known, deliberate limitation (documented in the P7.18 closure report,
not fixed here): PatternRepository has no id-based lookup independent of
`list_active()`/`get_latest(pattern_type)` - every PatternDetectionFlow
.respond() call persists a brand-new row (append-only, never an UPDATE),
so a pattern_id becomes unfindable the moment ANY response is recorded
against it. A second response using the same, now-stale pattern_id
therefore 404s, not 409 - unlike Experiment/Adaptation, whose
experiment_id/adaptation_id are stable, assigned-once business keys
`get_latest()` can always find regardless of status, so a repeated
action against those two correctly 409s instead.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_db_user, get_current_organization_id
from app.models.user import User
from app.schemas.personal_os_decisions import (
    AdaptationAction,
    AdaptationActionRequest,
    AdaptationDecisionDetail,
    DecisionDetail,
    DecisionListItem,
    DecisionListResponse,
    ExperimentAction,
    ExperimentActionRequest,
    ExperimentDecisionDetail,
    PatternAction,
    PatternActionRequest,
    PatternDecisionDetail,
)
from app.services.personal_os.adaptation import Adaptation
from app.services.personal_os.adaptation_flow import AdaptationFlow
from app.services.personal_os.adaptation_repository import AdaptationRepository
from app.services.personal_os.current_day import resolve_personal_os_today
from app.services.personal_os.decisions import (
    adaptation_allowed_actions,
    experiment_allowed_actions,
    is_adaptation_rollback_candidate,
    pattern_allowed_actions,
)
from app.services.personal_os.experiment import Experiment
from app.services.personal_os.experiment_flow import ExperimentFlow
from app.services.personal_os.pattern import Pattern
from app.services.personal_os.pattern_flow import PatternDetectionFlow
from app.services.personal_os.pattern_repository import PatternRepository
from app.services.personal_os.shared.types import AdaptationStatus, ExperimentStatus, ExperimentUserDecision, PatternStatus, UserPatternResponse
from app.services.personal_os.sql_repository import (
    SqlAdaptationRepository,
    SqlDailyIntentRepository,
    SqlEveningReflectionRepository,
    SqlExperimentRepository,
    SqlPatternRepository,
)
from database import get_db

router = APIRouter(prefix="/personal-os", tags=["personal-os-decisions"])


# --- flow construction (Sql*-backed repositories only, matching P7.17's own convention) --------


def _build_pattern_flow(db: Session, pattern_repository: PatternRepository) -> PatternDetectionFlow:
    return PatternDetectionFlow(
        intent_repository=SqlDailyIntentRepository(db), evening_repository=SqlEveningReflectionRepository(db), pattern_repository=pattern_repository
    )


def _build_experiment_flow(db: Session, experiment_repository: SqlExperimentRepository) -> ExperimentFlow:
    return ExperimentFlow(intent_repository=SqlDailyIntentRepository(db), evening_repository=SqlEveningReflectionRepository(db), experiment_repository=experiment_repository)


def _build_adaptation_flow(adaptation_repository: AdaptationRepository) -> AdaptationFlow:
    return AdaptationFlow(adaptation_repository=adaptation_repository)


def _find_pattern(pattern_repository: PatternRepository, *, organization_id: int, user_id: int, pattern_id: str) -> Pattern | None:
    """No repository method fetches a Pattern by id independent of
    status - list_active() (excludes only DISMISSED/SUPERSEDED) is the
    only tenant-scoped read available, so this is also, honestly, the
    only way a pattern currently awaiting a decision can be found."""
    for pattern in pattern_repository.list_active(organization_id=organization_id, user_id=user_id):
        if pattern.pattern_id == pattern_id:
            return pattern
    return None


def _get_outcome_experiment(experiment_repository: SqlExperimentRepository, adaptation: Adaptation, *, organization_id: int, user_id: int) -> Experiment | None:
    if not adaptation.outcome_experiment_id:
        return None
    return experiment_repository.get_latest(organization_id=organization_id, user_id=user_id, experiment_id=adaptation.outcome_experiment_id)


# --- domain -> API model conversions -------------------------------------------------------------


def _pattern_list_item(pattern: Pattern) -> DecisionListItem:
    return DecisionListItem(
        decision_type="pattern_confirmation",
        entity_type="pattern",
        entity_id=pattern.pattern_id,
        current_status=pattern.status.value,
        title="Tetra noticed a pattern",
        summary=pattern.pattern_statement,
        evidence=[fact.statement for fact in pattern.observed_facts],
        confidence=pattern.confidence.value,
        recommendation=pattern.recommendation.statement if pattern.recommendation else None,
        narrative=pattern.possible_hypotheses[0].statement if pattern.possible_hypotheses else None,
        allowed_actions=list(pattern_allowed_actions(pattern)),
        decision_required=True,
        created_at=pattern.created_at,
        updated_at=pattern.updated_at,
    )


def _pattern_detail(pattern: Pattern) -> PatternDecisionDetail:
    allowed = pattern_allowed_actions(pattern)
    return PatternDecisionDetail(
        entity_id=pattern.pattern_id,
        pattern_type=pattern.pattern_type.value,
        pattern_statement=pattern.pattern_statement,
        evidence=[fact.statement for fact in pattern.observed_facts],
        confidence=pattern.confidence.value,
        hypotheses=[h.statement for h in pattern.possible_hypotheses],
        user_interpretation=pattern.user_interpretation,
        recommendation=pattern.recommendation.statement if pattern.recommendation else None,
        status=pattern.status.value,
        allowed_actions=list(allowed),
        decision_required=bool(allowed),
        created_at=pattern.created_at,
        updated_at=pattern.updated_at,
    )


def _experiment_list_item(experiment: Experiment, decision_type: str) -> DecisionListItem:
    return DecisionListItem(
        decision_type=decision_type,
        entity_type="experiment",
        entity_id=experiment.experiment_id,
        current_status=experiment.status.value,
        title="Experiment ready for your decision" if decision_type == "experiment_review" else "Experiment awaiting approval",
        summary=experiment.hypothesis_statement,
        evidence=[experiment.comparison.observation_statement] if experiment.comparison else [],
        confidence=experiment.comparison.confidence.value if experiment.comparison else None,
        recommendation=experiment.review_outcome or None,
        narrative=experiment.review_narrative or None,
        allowed_actions=list(experiment_allowed_actions(experiment)),
        decision_required=True,
        created_at=experiment.created_at,
        updated_at=experiment.updated_at,
    )


def _experiment_detail(experiment: Experiment) -> ExperimentDecisionDetail:
    allowed = experiment_allowed_actions(experiment)
    return ExperimentDecisionDetail(
        entity_id=experiment.experiment_id,
        hypothesis_statement=experiment.hypothesis_statement,
        adjustment=experiment.adjustment,
        measurement_plan=experiment.measurement_plan,
        status=experiment.status.value,
        comparison_outcome=experiment.comparison.outcome.value if experiment.comparison else None,
        comparison_confidence=experiment.comparison.confidence.value if experiment.comparison else None,
        observation_statement=experiment.comparison.observation_statement if experiment.comparison else None,
        review_narrative=experiment.review_narrative,
        allowed_actions=list(allowed),
        decision_required=bool(allowed),
        created_at=experiment.created_at,
        updated_at=experiment.updated_at,
    )


def _adaptation_list_item(adaptation: Adaptation, decision_type: str, outcome_experiment: Experiment | None) -> DecisionListItem:
    titles = {
        "adaptation_approval": "Tetra recommends changing this behavior",
        "adaptation_adoption": "Approved adaptation ready to adopt",
        "adaptation_rollback": "An adopted change may not be helping",
    }
    recommendation = None
    if decision_type == "adaptation_rollback" and outcome_experiment is not None and outcome_experiment.comparison is not None:
        recommendation = outcome_experiment.review_outcome or outcome_experiment.comparison.observation_statement
    elif adaptation.expected_outcome:
        recommendation = adaptation.expected_outcome
    return DecisionListItem(
        decision_type=decision_type,
        entity_type="adaptation",
        entity_id=adaptation.adaptation_id,
        current_status=adaptation.status.value,
        title=titles[decision_type],
        summary=f"{adaptation.target.scope.value}: {adaptation.target.target_id}",
        evidence=[],
        confidence=adaptation.confidence.value,
        recommendation=recommendation,
        narrative=None,
        allowed_actions=list(adaptation_allowed_actions(adaptation)),
        decision_required=True,
        created_at=adaptation.created_at,
        updated_at=adaptation.updated_at,
    )


def _adaptation_detail(adaptation: Adaptation, outcome_experiment: Experiment | None) -> AdaptationDecisionDetail:
    allowed = adaptation_allowed_actions(adaptation)
    rollback_candidate = is_adaptation_rollback_candidate(adaptation, outcome_experiment)
    rollback_recommendation = None
    if rollback_candidate and outcome_experiment is not None:
        rollback_recommendation = outcome_experiment.review_outcome or (outcome_experiment.comparison.observation_statement if outcome_experiment.comparison else None)
    return AdaptationDecisionDetail(
        entity_id=adaptation.adaptation_id,
        target_scope=adaptation.target.scope.value,
        target_id=adaptation.target.target_id,
        expected_outcome=adaptation.expected_outcome,
        confidence=adaptation.confidence.value,
        status=adaptation.status.value,
        effect_kind=adaptation.effect.kind.value if adaptation.effect else None,
        effect_direction=adaptation.effect.direction.value if adaptation.effect else None,
        is_rollback_candidate=rollback_candidate,
        rollback_recommendation=rollback_recommendation,
        allowed_actions=list(allowed),
        decision_required=bool(allowed),
        created_at=adaptation.created_at,
        updated_at=adaptation.updated_at,
    )


# --- GET /personal-os/decisions -------------------------------------------------------------------


@router.get("/decisions", response_model=DecisionListResponse)
def list_decisions(
    user: User = Depends(get_current_db_user),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> DecisionListResponse:
    items: list[DecisionListItem] = []

    pattern_repository = SqlPatternRepository(db)
    for pattern in pattern_repository.list_active(organization_id=organization_id, user_id=user.id):
        if pattern.status == PatternStatus.PENDING_CONFIRMATION:
            items.append(_pattern_list_item(pattern))

    experiment_repository = SqlExperimentRepository(db)
    for experiment in experiment_repository.list_active(organization_id=organization_id, user_id=user.id):
        if experiment.status == ExperimentStatus.PROPOSED:
            items.append(_experiment_list_item(experiment, "experiment_approval"))
        elif experiment.status == ExperimentStatus.REVIEWED:
            items.append(_experiment_list_item(experiment, "experiment_review"))

    adaptation_repository = SqlAdaptationRepository(db)
    for adaptation in adaptation_repository.list_active(organization_id=organization_id, user_id=user.id):
        if adaptation.status in (AdaptationStatus.PROPOSED, AdaptationStatus.UNDER_EVALUATION):
            items.append(_adaptation_list_item(adaptation, "adaptation_approval", None))
        elif adaptation.status == AdaptationStatus.APPROVED:
            items.append(_adaptation_list_item(adaptation, "adaptation_adoption", None))
        elif adaptation.status == AdaptationStatus.ADOPTED:
            outcome_experiment = _get_outcome_experiment(experiment_repository, adaptation, organization_id=organization_id, user_id=user.id)
            if is_adaptation_rollback_candidate(adaptation, outcome_experiment):
                items.append(_adaptation_list_item(adaptation, "adaptation_rollback", outcome_experiment))

    # Deterministic, oldest-first ordering - matches every underlying
    # repository's own list_active() sort convention (sorted by
    # created_at); no priority scoring is introduced.
    items.sort(key=lambda item: item.created_at)
    return DecisionListResponse(items=items)


# --- GET /personal-os/decisions/{entity_type}/{entity_id} -----------------------------------------


@router.get("/decisions/{entity_type}/{entity_id}", response_model=DecisionDetail)
def get_decision_detail(
    entity_type: Literal["pattern", "experiment", "adaptation"],
    entity_id: str,
    user: User = Depends(get_current_db_user),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> PatternDecisionDetail | ExperimentDecisionDetail | AdaptationDecisionDetail:
    if entity_type == "pattern":
        pattern = _find_pattern(SqlPatternRepository(db), organization_id=organization_id, user_id=user.id, pattern_id=entity_id)
        if pattern is None:
            raise HTTPException(status_code=404, detail="Pattern not found")
        return _pattern_detail(pattern)

    if entity_type == "experiment":
        experiment = SqlExperimentRepository(db).get_latest(organization_id=organization_id, user_id=user.id, experiment_id=entity_id)
        if experiment is None:
            raise HTTPException(status_code=404, detail="Experiment not found")
        return _experiment_detail(experiment)

    adaptation_repository = SqlAdaptationRepository(db)
    adaptation = adaptation_repository.get_latest(organization_id=organization_id, user_id=user.id, adaptation_id=entity_id)
    if adaptation is None:
        raise HTTPException(status_code=404, detail="Adaptation not found")
    outcome_experiment = _get_outcome_experiment(SqlExperimentRepository(db), adaptation, organization_id=organization_id, user_id=user.id)
    return _adaptation_detail(adaptation, outcome_experiment)


# --- POST /personal-os/patterns/{pattern_id}/respond -----------------------------------------------


@router.post("/patterns/{pattern_id}/respond", response_model=PatternDecisionDetail)
def respond_to_pattern(
    pattern_id: str,
    payload: PatternActionRequest,
    user: User = Depends(get_current_db_user),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> PatternDecisionDetail:
    if payload.action == PatternAction.CORRECT and not payload.correction_text:
        raise HTTPException(status_code=422, detail="correction_text is required when action is 'correct'")

    pattern_repository = SqlPatternRepository(db)
    pattern = _find_pattern(pattern_repository, organization_id=organization_id, user_id=user.id, pattern_id=pattern_id)
    if pattern is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    if pattern.status != PatternStatus.PENDING_CONFIRMATION:
        raise HTTPException(status_code=409, detail=f"Pattern is not awaiting a decision (status={pattern.status.value})")

    flow = _build_pattern_flow(db, pattern_repository)
    response = UserPatternResponse(payload.action.value)
    try:
        updated = flow.respond(organization_id=organization_id, user_id=user.id, pattern=pattern, response=response, correction_text=payload.correction_text)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _pattern_detail(updated)


# --- POST /personal-os/experiments/{experiment_id}/respond -----------------------------------------


@router.post("/experiments/{experiment_id}/respond", response_model=ExperimentDecisionDetail)
def respond_to_experiment(
    experiment_id: str,
    payload: ExperimentActionRequest,
    user: User = Depends(get_current_db_user),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> ExperimentDecisionDetail:
    if payload.action == ExperimentAction.MODIFY and not payload.modification_notes:
        raise HTTPException(status_code=422, detail="modification_notes is required when action is 'modify'")
    if payload.action == ExperimentAction.CONTINUE and payload.extended_review_date is None:
        raise HTTPException(status_code=422, detail="extended_review_date is required when action is 'continue'")

    experiment_repository = SqlExperimentRepository(db)
    experiment = experiment_repository.get_latest(organization_id=organization_id, user_id=user.id, experiment_id=experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    flow = _build_experiment_flow(db, experiment_repository)
    action = payload.action

    try:
        if action in ("approve", "reject"):
            if experiment.status != ExperimentStatus.PROPOSED:
                raise HTTPException(status_code=409, detail=f"Experiment is not awaiting approval (status={experiment.status.value})")
            if action == "approve":
                updated = flow.approve(organization_id=organization_id, user_id=user.id, experiment=experiment)
            else:
                updated = flow.reject(organization_id=organization_id, user_id=user.id, experiment=experiment, reason=payload.reason)
        else:
            if experiment.status != ExperimentStatus.REVIEWED:
                raise HTTPException(status_code=409, detail=f"Experiment is not awaiting a post-review decision (status={experiment.status.value})")
            updated = flow.decide(
                organization_id=organization_id,
                user_id=user.id,
                experiment=experiment,
                decision=ExperimentUserDecision(action),
                today=resolve_personal_os_today(),
                reason=payload.reason,
                modification_notes=payload.modification_notes,
                extended_review_date=payload.extended_review_date,
            )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return _experiment_detail(updated)


# --- POST /personal-os/adaptations/{adaptation_id}/respond -----------------------------------------


@router.post("/adaptations/{adaptation_id}/respond", response_model=AdaptationDecisionDetail)
def respond_to_adaptation(
    adaptation_id: str,
    payload: AdaptationActionRequest,
    user: User = Depends(get_current_db_user),
    organization_id: int = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> AdaptationDecisionDetail:
    if payload.action in (AdaptationAction.REJECT, AdaptationAction.ROLLBACK) and not payload.reason:
        raise HTTPException(status_code=422, detail="reason is required for this action")

    adaptation_repository = SqlAdaptationRepository(db)
    adaptation = adaptation_repository.get_latest(organization_id=organization_id, user_id=user.id, adaptation_id=adaptation_id)
    if adaptation is None:
        raise HTTPException(status_code=404, detail="Adaptation not found")

    flow = _build_adaptation_flow(adaptation_repository)
    action = payload.action

    try:
        if action == AdaptationAction.APPROVE:
            if adaptation.status not in (AdaptationStatus.PROPOSED, AdaptationStatus.UNDER_EVALUATION):
                raise HTTPException(status_code=409, detail=f"Adaptation is not awaiting approval (status={adaptation.status.value})")
            updated = flow.approve(adaptation, organization_id=organization_id, user_id=user.id, reason=payload.reason)
        elif action == AdaptationAction.REJECT:
            if adaptation.status not in (AdaptationStatus.PROPOSED, AdaptationStatus.UNDER_EVALUATION, AdaptationStatus.APPROVED):
                raise HTTPException(status_code=409, detail=f"Adaptation cannot be rejected from its current state (status={adaptation.status.value})")
            updated = flow.reject(adaptation, organization_id=organization_id, user_id=user.id, reason=payload.reason)
        elif action == AdaptationAction.ADOPT:
            if adaptation.status != AdaptationStatus.APPROVED:
                raise HTTPException(status_code=409, detail=f"Adaptation is not awaiting adoption (status={adaptation.status.value})")
            updated = flow.adopt(adaptation, organization_id=organization_id, user_id=user.id)
        else:
            if adaptation.status != AdaptationStatus.ADOPTED:
                raise HTTPException(status_code=409, detail=f"Adaptation is not adopted, so it cannot be rolled back (status={adaptation.status.value})")
            updated = flow.rollback(adaptation, organization_id=organization_id, user_id=user.id, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    outcome_experiment = _get_outcome_experiment(SqlExperimentRepository(db), updated, organization_id=organization_id, user_id=user.id)
    return _adaptation_detail(updated, outcome_experiment)
