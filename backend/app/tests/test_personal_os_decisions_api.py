"""P7.18: real end-to-end API tests for Personal OS's governance surface
- real HTTP, real authentication, real tenant scoping, real flow methods
underneath. State is seeded directly via the Sql*Repository classes
(exactly as Personal OS's own flow-level tests already do), since
reaching PENDING_CONFIRMATION/PROPOSED/REVIEWED states through the real
detection/proposal pipeline would require far more setup than these
governance-surface tests are actually about."""

from datetime import date

import pytest

from app.models.user import User
from app.services.personal_os.adaptation import Adaptation, AdaptationEffect, AdaptationTarget
from app.services.personal_os.experiment import Experiment, ExperimentBaseline, ExperimentComparison, ExperimentMeasurement
from app.services.personal_os.pattern import Pattern
from app.services.personal_os.reasoning import GrowthRecommendation, Hypothesis, InferredPattern, ObservedFact
from app.services.personal_os.shared.types import (
    AdaptationEffectKind,
    AdaptationScope,
    AdaptationStatus,
    Confidence,
    ExperimentOutcome,
    ExperimentStatus,
    PatternStatus,
    PatternType,
    PriorityDirection,
)
from app.services.personal_os.sql_repository import SqlAdaptationRepository, SqlExperimentRepository, SqlPatternRepository


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def token(make_user, org_id):
    return make_user("alice", org_id)


@pytest.fixture()
def user_id(db_session, token):
    return db_session.query(User).filter(User.username == "alice").one().id


def _pattern(status: PatternStatus, pattern_type: PatternType = PatternType.REPEATED_POSTPONEMENT, recommendation=None) -> Pattern:
    return Pattern(
        pattern_id="", pattern_type=pattern_type, observation_window_start=date(2026, 1, 1), observation_window_end=date(2026, 1, 7),
        evidence=(), observed_facts=(), pattern_statement="You postponed the same task three times.", confidence=Confidence.MEDIUM,
        status=status, recommendation=recommendation,
    )


def _baseline() -> ExperimentBaseline:
    return ExperimentBaseline(metric="hours", category="work", period_start=date(2026, 1, 1), period_end=date(2026, 1, 7), value=10.0, observation_count=5)


def _measurement() -> ExperimentMeasurement:
    return ExperimentMeasurement(metric="hours", category="work", period_start=date(2026, 1, 8), period_end=date(2026, 1, 14), value=6.0, observation_count=5)


def _comparison(outcome: ExperimentOutcome) -> ExperimentComparison:
    return ExperimentComparison(
        baseline=_baseline(), measurement=_measurement(), absolute_change=-4.0, relative_change=-0.4, outcome=outcome, confidence=Confidence.MEDIUM, observation_statement="Hours dropped."
    )


def _experiment(status: ExperimentStatus, comparison=None) -> Experiment:
    return Experiment(
        experiment_id="", pattern_id="p1", hypothesis_statement="Reducing scope helps.", adjustment="Cap daily tasks at 3.", measurement_plan="Compare hours/week.",
        baseline=_baseline(), started_on=date(2026, 1, 1), status=status, comparison=comparison,
    )


def _adaptation(status: AdaptationStatus, outcome_experiment_id: str | None = None, effect=None) -> Adaptation:
    return Adaptation(
        adaptation_id="", target=AdaptationTarget(scope=AdaptationScope.USER, target_id="1"), pattern_id="p1", confidence=Confidence.MEDIUM,
        expected_outcome="Fewer postponed tasks.", status=status, outcome_experiment_id=outcome_experiment_id, effect=effect,
    )


# --- AUTHENTICATION --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "/api/v1/personal-os/decisions", None),
        ("get", "/api/v1/personal-os/decisions/pattern/x", None),
        ("post", "/api/v1/personal-os/patterns/x/respond", {"action": "confirm"}),
        ("post", "/api/v1/personal-os/experiments/x/respond", {"action": "approve"}),
        ("post", "/api/v1/personal-os/adaptations/x/respond", {"action": "approve"}),
    ],
)
def test_all_five_endpoints_reject_unauthenticated_requests(client, org_id, method, path, body):
    call = getattr(client, method)
    response = call(path, json=body) if body is not None else call(path)
    assert response.status_code == 401


# --- EMPTY -----------------------------------------------------------------------------------


def test_decisions_list_is_empty_for_a_brand_new_account(client, org_id, token):
    response = client.get("/api/v1/personal-os/decisions", headers=_headers(token))
    assert response.status_code == 200
    assert response.json() == {"items": []}


# --- PATTERN -----------------------------------------------------------------------------------


def test_pending_confirmation_pattern_appears_in_decisions(client, org_id, user_id, db_session, token):
    SqlPatternRepository(db_session).save(_pattern(PatternStatus.PENDING_CONFIRMATION), organization_id=org_id, user_id=user_id)
    response = client.get("/api/v1/personal-os/decisions", headers=_headers(token))
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["decision_type"] == "pattern_confirmation"
    assert items[0]["entity_type"] == "pattern"
    assert set(items[0]["allowed_actions"]) == {"confirm", "reject", "correct", "defer"}


def test_observed_pattern_does_not_appear_in_decisions(client, org_id, user_id, db_session, token):
    SqlPatternRepository(db_session).save(_pattern(PatternStatus.OBSERVED), organization_id=org_id, user_id=user_id)
    response = client.get("/api/v1/personal-os/decisions", headers=_headers(token))
    assert response.json()["items"] == []


def test_get_decisions_does_not_mutate_the_observed_pattern(client, org_id, user_id, db_session, token):
    """Read purity (§4/§29): GET /decisions must never call surface_next()
    itself or as a hidden side effect."""
    pattern_repo = SqlPatternRepository(db_session)
    pattern_repo.save(_pattern(PatternStatus.OBSERVED), organization_id=org_id, user_id=user_id)
    client.get("/api/v1/personal-os/decisions", headers=_headers(token))
    client.get("/api/v1/personal-os/decisions", headers=_headers(token))
    remaining = pattern_repo.list_active(organization_id=org_id, user_id=user_id)
    assert len(remaining) == 1
    assert remaining[0].status == PatternStatus.OBSERVED


def test_confirm_pattern_succeeds(client, org_id, user_id, db_session, token):
    pattern_repo = SqlPatternRepository(db_session)
    pattern_repo.save(_pattern(PatternStatus.PENDING_CONFIRMATION), organization_id=org_id, user_id=user_id)
    pattern_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.post(f"/api/v1/personal-os/patterns/{pattern_id}/respond", json={"action": "confirm"}, headers=_headers(token))
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert response.json()["allowed_actions"] == []


def test_reject_pattern_succeeds(client, org_id, user_id, db_session, token):
    pattern_repo = SqlPatternRepository(db_session)
    pattern_repo.save(_pattern(PatternStatus.PENDING_CONFIRMATION), organization_id=org_id, user_id=user_id)
    pattern_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.post(f"/api/v1/personal-os/patterns/{pattern_id}/respond", json={"action": "reject"}, headers=_headers(token))
    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"


def test_correct_pattern_without_correction_text_returns_422(client, org_id, user_id, db_session, token):
    pattern_repo = SqlPatternRepository(db_session)
    pattern_repo.save(_pattern(PatternStatus.PENDING_CONFIRMATION), organization_id=org_id, user_id=user_id)
    pattern_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.post(f"/api/v1/personal-os/patterns/{pattern_id}/respond", json={"action": "correct"}, headers=_headers(token))
    assert response.status_code == 422


def test_correct_pattern_with_correction_text_succeeds(client, org_id, user_id, db_session, token):
    pattern_repo = SqlPatternRepository(db_session)
    pattern_repo.save(_pattern(PatternStatus.PENDING_CONFIRMATION), organization_id=org_id, user_id=user_id)
    pattern_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.post(
        f"/api/v1/personal-os/patterns/{pattern_id}/respond", json={"action": "correct", "correction_text": "It's actually about a different task."}, headers=_headers(token)
    )
    assert response.status_code == 200
    assert response.json()["status"] == "corrected"
    assert response.json()["user_interpretation"] == "It's actually about a different task."


def test_defer_pattern_leaves_it_exactly_as_pending(client, org_id, user_id, db_session, token):
    pattern_repo = SqlPatternRepository(db_session)
    pattern_repo.save(_pattern(PatternStatus.PENDING_CONFIRMATION), organization_id=org_id, user_id=user_id)
    pattern_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.post(f"/api/v1/personal-os/patterns/{pattern_id}/respond", json={"action": "defer"}, headers=_headers(token))
    assert response.status_code == 200
    assert response.json()["status"] == "pending_confirmation"
    # still appears in the decisions list, unresolved
    assert len(client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"]) == 1


def test_repeated_pattern_response_returns_404_not_409(client, org_id, user_id, db_session, token):
    """Documented deviation from the brief's literal expectation: unlike
    Experiment/Adaptation, PatternRecord has no stable id-independent-of-
    status lookup - every respond() call is a brand-new row, so the
    ORIGINAL pattern_id is genuinely unfindable after the first response,
    not merely status-conflicted. See personal_os_decisions.py's own
    module docstring for the full architectural reason."""
    pattern_repo = SqlPatternRepository(db_session)
    pattern_repo.save(_pattern(PatternStatus.PENDING_CONFIRMATION), organization_id=org_id, user_id=user_id)
    pattern_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    first = client.post(f"/api/v1/personal-os/patterns/{pattern_id}/respond", json={"action": "confirm"}, headers=_headers(token))
    assert first.status_code == 200

    second = client.post(f"/api/v1/personal-os/patterns/{pattern_id}/respond", json={"action": "confirm"}, headers=_headers(token))
    assert second.status_code == 404


# --- EXPERIMENT APPROVAL --------------------------------------------------------------------------


def test_proposed_experiment_appears_as_experiment_approval(client, org_id, user_id, db_session, token):
    SqlExperimentRepository(db_session).save(_experiment(ExperimentStatus.PROPOSED), organization_id=org_id, user_id=user_id)
    items = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"]
    assert len(items) == 1
    assert items[0]["decision_type"] == "experiment_approval"
    assert set(items[0]["allowed_actions"]) == {"approve", "reject"}


def test_approve_experiment_succeeds(client, org_id, user_id, db_session, token):
    experiment_repo = SqlExperimentRepository(db_session)
    experiment_repo.save(_experiment(ExperimentStatus.PROPOSED), organization_id=org_id, user_id=user_id)
    experiment_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.post(f"/api/v1/personal-os/experiments/{experiment_id}/respond", json={"action": "approve"}, headers=_headers(token))
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_reject_experiment_succeeds(client, org_id, user_id, db_session, token):
    experiment_repo = SqlExperimentRepository(db_session)
    experiment_repo.save(_experiment(ExperimentStatus.PROPOSED), organization_id=org_id, user_id=user_id)
    experiment_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.post(f"/api/v1/personal-os/experiments/{experiment_id}/respond", json={"action": "reject", "reason": "not worth trying"}, headers=_headers(token))
    assert response.status_code == 200
    assert response.json()["status"] == "stopped"


def test_repeat_approve_after_approval_returns_409(client, org_id, user_id, db_session, token):
    experiment_repo = SqlExperimentRepository(db_session)
    experiment_repo.save(_experiment(ExperimentStatus.PROPOSED), organization_id=org_id, user_id=user_id)
    experiment_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    first = client.post(f"/api/v1/personal-os/experiments/{experiment_id}/respond", json={"action": "approve"}, headers=_headers(token))
    assert first.status_code == 200
    second = client.post(f"/api/v1/personal-os/experiments/{experiment_id}/respond", json={"action": "approve"}, headers=_headers(token))
    assert second.status_code == 409


# --- EXPERIMENT POST-REVIEW ------------------------------------------------------------------------


def test_reviewed_experiment_appears_as_experiment_review(client, org_id, user_id, db_session, token):
    SqlExperimentRepository(db_session).save(_experiment(ExperimentStatus.REVIEWED, _comparison(ExperimentOutcome.IMPROVED)), organization_id=org_id, user_id=user_id)
    items = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"]
    assert len(items) == 1
    assert items[0]["decision_type"] == "experiment_review"
    assert set(items[0]["allowed_actions"]) == {"keep", "modify", "stop", "continue", "defer"}
    assert items[0]["confidence"] == "medium"


@pytest.mark.parametrize(
    "action,extra",
    [
        ("keep", {}),
        ("stop", {}),
        ("defer", {}),
        ("continue", {"extended_review_date": "2026-02-01"}),
        ("modify", {"modification_notes": "Cap at 2 tasks instead of 3."}),
    ],
)
def test_each_post_review_decision_succeeds(client, org_id, user_id, db_session, token, action, extra):
    SqlExperimentRepository(db_session).save(_experiment(ExperimentStatus.REVIEWED, _comparison(ExperimentOutcome.IMPROVED)), organization_id=org_id, user_id=user_id)
    experiment_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.post(f"/api/v1/personal-os/experiments/{experiment_id}/respond", json={"action": action, **extra}, headers=_headers(token))
    assert response.status_code == 200


def test_continue_without_extended_review_date_returns_422(client, org_id, user_id, db_session, token):
    SqlExperimentRepository(db_session).save(_experiment(ExperimentStatus.REVIEWED, _comparison(ExperimentOutcome.IMPROVED)), organization_id=org_id, user_id=user_id)
    experiment_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.post(f"/api/v1/personal-os/experiments/{experiment_id}/respond", json={"action": "continue"}, headers=_headers(token))
    assert response.status_code == 422


def test_modify_without_modification_notes_returns_422(client, org_id, user_id, db_session, token):
    SqlExperimentRepository(db_session).save(_experiment(ExperimentStatus.REVIEWED, _comparison(ExperimentOutcome.IMPROVED)), organization_id=org_id, user_id=user_id)
    experiment_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.post(f"/api/v1/personal-os/experiments/{experiment_id}/respond", json={"action": "modify"}, headers=_headers(token))
    assert response.status_code == 422


def test_approve_action_against_a_reviewed_experiment_returns_409(client, org_id, user_id, db_session, token):
    SqlExperimentRepository(db_session).save(_experiment(ExperimentStatus.REVIEWED, _comparison(ExperimentOutcome.IMPROVED)), organization_id=org_id, user_id=user_id)
    experiment_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.post(f"/api/v1/personal-os/experiments/{experiment_id}/respond", json={"action": "approve"}, headers=_headers(token))
    assert response.status_code == 409


# --- ADAPTATION -----------------------------------------------------------------------------------


@pytest.mark.parametrize("status", [AdaptationStatus.PROPOSED, AdaptationStatus.UNDER_EVALUATION])
def test_proposed_or_under_evaluation_adaptation_appears_as_adaptation_approval(client, org_id, user_id, db_session, token, status):
    SqlAdaptationRepository(db_session).save(_adaptation(status), organization_id=org_id, user_id=user_id)
    items = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"]
    assert len(items) == 1
    assert items[0]["decision_type"] == "adaptation_approval"
    assert set(items[0]["allowed_actions"]) == {"approve", "reject"}


def test_approve_adaptation_succeeds(client, org_id, user_id, db_session, token):
    adaptation_repo = SqlAdaptationRepository(db_session)
    adaptation_repo.save(_adaptation(AdaptationStatus.PROPOSED), organization_id=org_id, user_id=user_id)
    adaptation_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.post(f"/api/v1/personal-os/adaptations/{adaptation_id}/respond", json={"action": "approve"}, headers=_headers(token))
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_reject_adaptation_without_reason_returns_422(client, org_id, user_id, db_session, token):
    adaptation_repo = SqlAdaptationRepository(db_session)
    adaptation_repo.save(_adaptation(AdaptationStatus.PROPOSED), organization_id=org_id, user_id=user_id)
    adaptation_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.post(f"/api/v1/personal-os/adaptations/{adaptation_id}/respond", json={"action": "reject"}, headers=_headers(token))
    assert response.status_code == 422


def test_reject_adaptation_with_reason_succeeds(client, org_id, user_id, db_session, token):
    adaptation_repo = SqlAdaptationRepository(db_session)
    adaptation_repo.save(_adaptation(AdaptationStatus.PROPOSED), organization_id=org_id, user_id=user_id)
    adaptation_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.post(f"/api/v1/personal-os/adaptations/{adaptation_id}/respond", json={"action": "reject", "reason": "not evidence-backed enough"}, headers=_headers(token))
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_approved_adaptation_appears_as_adaptation_adoption_and_adopt_succeeds(client, org_id, user_id, db_session, token):
    adaptation_repo = SqlAdaptationRepository(db_session)
    adaptation_repo.save(_adaptation(AdaptationStatus.APPROVED), organization_id=org_id, user_id=user_id)
    items = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"]
    assert items[0]["decision_type"] == "adaptation_adoption"
    assert items[0]["allowed_actions"] == ["adopt"]

    response = client.post(f"/api/v1/personal-os/adaptations/{items[0]['entity_id']}/respond", json={"action": "adopt"}, headers=_headers(token))
    assert response.status_code == 200
    assert response.json()["status"] == "adopted"


def test_adopted_adaptation_with_no_outcome_signal_is_not_in_decisions(client, org_id, user_id, db_session, token):
    SqlAdaptationRepository(db_session).save(_adaptation(AdaptationStatus.ADOPTED), organization_id=org_id, user_id=user_id)
    assert client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"] == []


def test_adopted_adaptation_with_improved_outcome_is_not_in_decisions(client, org_id, user_id, db_session, token):
    """The linked outcome experiment itself is still REVIEWED, so it
    legitimately appears as its own, independent experiment_review
    decision - only the ADAPTATION's own rollback candidacy is what's
    being asserted absent here."""
    experiment_repo = SqlExperimentRepository(db_session)
    outcome = experiment_repo.save(_experiment(ExperimentStatus.REVIEWED, _comparison(ExperimentOutcome.IMPROVED)), organization_id=org_id, user_id=user_id)
    SqlAdaptationRepository(db_session).save(_adaptation(AdaptationStatus.ADOPTED, outcome_experiment_id=outcome.experiment_id), organization_id=org_id, user_id=user_id)

    items = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"]
    decision_types = {item["decision_type"] for item in items}
    assert "adaptation_rollback" not in decision_types
    assert decision_types == {"experiment_review"}


def test_adopted_adaptation_with_worsened_outcome_appears_as_rollback_candidate(client, org_id, user_id, db_session, token):
    """Two independent, correctly-distinct decisions surface here: the
    outcome experiment's own experiment_review (someone must still
    keep/modify/stop/continue/defer IT), and the adaptation's own
    adaptation_rollback candidacy - never collapsed into one."""
    experiment_repo = SqlExperimentRepository(db_session)
    outcome = experiment_repo.save(_experiment(ExperimentStatus.REVIEWED, _comparison(ExperimentOutcome.WORSENED)), organization_id=org_id, user_id=user_id)
    SqlAdaptationRepository(db_session).save(_adaptation(AdaptationStatus.ADOPTED, outcome_experiment_id=outcome.experiment_id), organization_id=org_id, user_id=user_id)

    items = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"]
    assert len(items) == 2
    decision_types = {item["decision_type"] for item in items}
    assert decision_types == {"experiment_review", "adaptation_rollback"}
    rollback_item = next(item for item in items if item["decision_type"] == "adaptation_rollback")
    assert rollback_item["allowed_actions"] == ["rollback"]


def test_explicit_rollback_on_a_non_flagged_adopted_adaptation_still_works(client, org_id, user_id, db_session, token):
    """§18: rollback is a real action a user can take on any specific
    ADOPTED adaptation they explicitly address - never gated behind
    whether it happened to be flagged as a rollback candidate in the
    list."""
    adaptation_repo = SqlAdaptationRepository(db_session)
    adapted = adaptation_repo.save(_adaptation(AdaptationStatus.ADOPTED), organization_id=org_id, user_id=user_id)
    assert client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"] == []

    response = client.post(f"/api/v1/personal-os/adaptations/{adapted.adaptation_id}/respond", json={"action": "rollback", "reason": "user preference"}, headers=_headers(token))
    assert response.status_code == 200
    assert response.json()["status"] == "rolled_back"


def test_rollback_without_reason_returns_422(client, org_id, user_id, db_session, token):
    adaptation_repo = SqlAdaptationRepository(db_session)
    adapted = adaptation_repo.save(_adaptation(AdaptationStatus.ADOPTED), organization_id=org_id, user_id=user_id)
    response = client.post(f"/api/v1/personal-os/adaptations/{adapted.adaptation_id}/respond", json={"action": "rollback"}, headers=_headers(token))
    assert response.status_code == 422


def test_rollback_on_a_non_adopted_adaptation_returns_409(client, org_id, user_id, db_session, token):
    adaptation_repo = SqlAdaptationRepository(db_session)
    proposed = adaptation_repo.save(_adaptation(AdaptationStatus.PROPOSED), organization_id=org_id, user_id=user_id)
    response = client.post(f"/api/v1/personal-os/adaptations/{proposed.adaptation_id}/respond", json={"action": "rollback", "reason": "x"}, headers=_headers(token))
    assert response.status_code == 409


# --- DETAIL ------------------------------------------------------------------------------------------


def test_pattern_detail_returns_structured_detail(client, org_id, user_id, db_session, token):
    inferred = InferredPattern(statement="Repeated postponement", supporting_facts=(ObservedFact("a"), ObservedFact("b")))
    hypothesis = Hypothesis(statement="May indicate low priority.", explains=inferred)
    recommendation = GrowthRecommendation(statement="Try batching similar tasks.", responds_to=hypothesis)
    SqlPatternRepository(db_session).save(_pattern(PatternStatus.PENDING_CONFIRMATION, recommendation=recommendation), organization_id=org_id, user_id=user_id)
    pattern_id = client.get("/api/v1/personal-os/decisions", headers=_headers(token)).json()["items"][0]["entity_id"]

    response = client.get(f"/api/v1/personal-os/decisions/pattern/{pattern_id}", headers=_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["entity_type"] == "pattern"
    assert body["recommendation"] == "Try batching similar tasks."
    assert body["decision_required"] is True


def test_adaptation_detail_reports_effect_when_present(client, org_id, user_id, db_session, token):
    effect = AdaptationEffect(kind=AdaptationEffectKind.PRIORITY_ADJUSTMENT, direction=PriorityDirection.SUPPRESS)
    adaptation_repo = SqlAdaptationRepository(db_session)
    adapted = adaptation_repo.save(_adaptation(AdaptationStatus.PROPOSED, effect=effect), organization_id=org_id, user_id=user_id)

    response = client.get(f"/api/v1/personal-os/decisions/adaptation/{adapted.adaptation_id}", headers=_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["effect_kind"] == "priority_adjustment"
    assert body["effect_direction"] == "suppress"


def test_detail_404_for_missing_entity(client, org_id, token):
    response = client.get("/api/v1/personal-os/decisions/experiment/does-not-exist", headers=_headers(token))
    assert response.status_code == 404


def test_detail_422_for_unknown_entity_type(client, org_id, token):
    response = client.get("/api/v1/personal-os/decisions/mission/1", headers=_headers(token))
    assert response.status_code == 422


# --- TENANT --------------------------------------------------------------------------------------


def test_cross_tenant_detail_returns_404(client, org_id, user_id, db_session, make_user):
    SqlPatternRepository(db_session).save(_pattern(PatternStatus.PENDING_CONFIRMATION), organization_id=org_id, user_id=user_id)
    pattern_id = SqlPatternRepository(db_session).list_active(organization_id=org_id, user_id=user_id)[0].pattern_id

    org_b = client.post("/api/v1/organizations", json={"name": "Org B", "slug": "org-b-decisions"}).json()["id"]
    token_b = make_user("bob", org_b)

    response = client.get(f"/api/v1/personal-os/decisions/pattern/{pattern_id}", headers=_headers(token_b))
    assert response.status_code == 404


def test_cross_tenant_cannot_see_or_act_on_another_orgs_experiment(client, org_id, user_id, db_session, make_user):
    experiment = SqlExperimentRepository(db_session).save(_experiment(ExperimentStatus.PROPOSED), organization_id=org_id, user_id=user_id)

    org_b = client.post("/api/v1/organizations", json={"name": "Org C", "slug": "org-c-decisions"}).json()["id"]
    token_b = make_user("carol", org_b)

    assert client.get("/api/v1/personal-os/decisions", headers=_headers(token_b)).json()["items"] == []
    response = client.post(f"/api/v1/personal-os/experiments/{experiment.experiment_id}/respond", json={"action": "approve"}, headers=_headers(token_b))
    assert response.status_code == 404
