"""PatternDetectionFlow (P3 §11-§13, §16): the confirmation model
(confirm/reject/correct/defer), the recommendation model, experimental
learning, and the safety-of-personal-inference language rules."""

from datetime import date

import pytest

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.runtime.types import RuntimeResponse
from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.evening import EveningReflection, InMemoryEveningReflectionRepository
from app.services.personal_os.pattern_evidence import EvidenceWindow
from app.services.personal_os.pattern_flow import PatternDetectionFlow
from app.services.personal_os.pattern_repository import InMemoryPatternRepository
from app.services.personal_os.reasoning import GrowthRecommendation
from app.services.personal_os.reconciliation import ReconciliationEvidence, reconcile_all
from app.services.personal_os.repository import InMemoryDailyIntentRepository
from app.services.personal_os.shared.types import DayType, PatternStatus, UserPatternResponse

ORG_ID, USER_ID = 1, 2


class _FakeRuntime:
    """Mirrors evening_flow's own _FakeRuntime exactly - deliberately
    returns success=False so tests exercise the honest, deterministic
    fallback narration path rather than depending on any real provider."""

    def __init__(self):
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return RuntimeResponse(success=False)


def _flow(*, min_observations=3):
    from app.services.personal_os.pattern_detectors import PatternDetectionConfig

    intent_repo = InMemoryDailyIntentRepository()
    evening_repo = InMemoryEveningReflectionRepository()
    pattern_repo = InMemoryPatternRepository()
    flow = PatternDetectionFlow(
        intent_repo,
        evening_repo,
        pattern_repo,
        runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()),
        config=PatternDetectionConfig(min_observations=min_observations),
    )
    return flow, intent_repo, evening_repo, pattern_repo


def _seed_postponed_days(intent_repo, evening_repo, days, description="Study transformers", reason="ran out of time"):
    for d in days:
        day = date(2026, 7, d)
        activity = PlannedActivity(description=description, focus_area="learning")
        intent = DailyIntent(intent_date=day, stated_intention="x", day_type=DayType.STUDY, planned_activities=(activity,))
        intent_repo.save(intent, organization_id=ORG_ID, user_id=USER_ID)
        evidence = {description: ReconciliationEvidence(explicitly_postponed=True, note=reason)}
        reflection = EveningReflection(reflection_date=day, accomplishments=(), evidence_by_activity_description=evidence)
        reconciliations = reconcile_all((activity,), evidence)
        evening_repo.save(reflection, reconciliations, organization_id=ORG_ID, user_id=USER_ID, daily_intent_id=intent.intent_id)


def _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo, days=(1, 3, 5, 8)):
    _seed_postponed_days(intent_repo, evening_repo, days)
    flow.detect(organization_id=ORG_ID, user_id=USER_ID, today=date(2026, 7, 15))
    return flow.surface_next(organization_id=ORG_ID, user_id=USER_ID)


# --- the full real flow (§22's own closing instruction) -----------------------------------------


def test_the_complete_flow_from_historical_evidence_to_measurement():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)

    assert surfacing is not None
    assert surfacing.pattern.observation_count == 4
    assert surfacing.confidence_statement == "Confidence: medium."
    assert surfacing.confirmation_question == "Does that seem accurate to you?"

    confirmed = flow.respond(organization_id=ORG_ID, user_id=USER_ID, pattern=surfacing.pattern, response=UserPatternResponse.CONFIRM)
    assert confirmed.status == PatternStatus.CONFIRMED

    recommendation = GrowthRecommendation(
        statement="Consider adding a buffer to time estimates for learning activities.",
        responds_to=confirmed.possible_hypotheses[0],
    )
    with_recommendation = flow.attach_recommendation(organization_id=ORG_ID, user_id=USER_ID, pattern=confirmed, recommendation=recommendation)
    assert with_recommendation.recommendation is recommendation

    experiment = flow.propose_experiment(
        with_recommendation,
        organization_id=ORG_ID,
        user_id=USER_ID,
        hypothesis_statement="A larger buffer will reduce postponement of learning activities.",
        adjustment="Add a 50% buffer to learning-category estimates.",
        measurement_plan="Re-run detection after 14 more days and compare postponement counts.",
        metric="postponement_count",
        category="learning",
        baseline_window=EvidenceWindow(start=date(2026, 7, 1), end=date(2026, 7, 14)),
        started_on=date(2026, 7, 16),
        review_date=date(2026, 7, 30),
    )
    assert experiment.pattern_id == with_recommendation.pattern_id
    assert experiment.measurement_plan
    assert experiment.baseline.value == 4
    assert experiment.experiment_id != ""


# --- surfacing (§11) -------------------------------------------------------------------------------


def test_surface_next_returns_none_when_nothing_is_pending():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    assert flow.surface_next(organization_id=ORG_ID, user_id=USER_ID) is None


def test_surface_next_moves_status_from_observed_to_pending_confirmation():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    assert surfacing.pattern.status == PatternStatus.PENDING_CONFIRMATION


def test_surface_next_does_not_resurface_a_pattern_already_pending():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    assert flow.surface_next(organization_id=ORG_ID, user_id=USER_ID) is None


def test_narrative_falls_back_to_deterministic_phrasing_when_the_runtime_fails():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    assert "I've noticed something" in surfacing.narrative
    assert "Does that seem accurate to you?" in surfacing.narrative


# --- confirmation model (§11, §17) ----------------------------------------------------------------


def test_confirm_transitions_a_pattern_to_confirmed():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    confirmed = flow.respond(organization_id=ORG_ID, user_id=USER_ID, pattern=surfacing.pattern, response=UserPatternResponse.CONFIRM)
    assert confirmed.status == PatternStatus.CONFIRMED


def test_reject_transitions_a_pattern_to_dismissed():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    rejected = flow.respond(organization_id=ORG_ID, user_id=USER_ID, pattern=surfacing.pattern, response=UserPatternResponse.REJECT)
    assert rejected.status == PatternStatus.DISMISSED


def test_a_rejected_pattern_is_never_surfaced_again_as_established_fact():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    flow.respond(organization_id=ORG_ID, user_id=USER_ID, pattern=surfacing.pattern, response=UserPatternResponse.REJECT)

    active = pattern_repo.list_active(organization_id=ORG_ID, user_id=USER_ID)
    assert active == ()
    assert flow.surface_next(organization_id=ORG_ID, user_id=USER_ID) is None


def test_correct_transitions_a_pattern_to_corrected_and_preserves_the_users_words():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    corrected = flow.respond(
        organization_id=ORG_ID,
        user_id=USER_ID,
        pattern=surfacing.pattern,
        response=UserPatternResponse.CORRECT,
        correction_text="Actually this was a family emergency, not optimistic time estimates.",
    )
    assert corrected.status == PatternStatus.CORRECTED
    assert corrected.user_interpretation == "Actually this was a family emergency, not optimistic time estimates."


def test_correct_without_correction_text_raises():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    with pytest.raises(ValueError):
        flow.respond(organization_id=ORG_ID, user_id=USER_ID, pattern=surfacing.pattern, response=UserPatternResponse.CORRECT)


def test_corrected_patterns_stop_being_treated_as_confirmed():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    corrected = flow.respond(
        organization_id=ORG_ID, user_id=USER_ID, pattern=surfacing.pattern, response=UserPatternResponse.CORRECT, correction_text="Not accurate."
    )
    assert corrected.status != PatternStatus.CONFIRMED
    with pytest.raises(ValueError):
        flow.attach_recommendation(
            organization_id=ORG_ID,
            user_id=USER_ID,
            pattern=corrected,
            recommendation=GrowthRecommendation(statement="x", responds_to=corrected.possible_hypotheses[0]),
        )


def test_defer_leaves_the_pattern_unchanged_and_still_pending():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    deferred = flow.respond(organization_id=ORG_ID, user_id=USER_ID, pattern=surfacing.pattern, response=UserPatternResponse.DEFER)
    assert deferred.status == PatternStatus.PENDING_CONFIRMATION
    assert deferred is surfacing.pattern


# --- recommendation model (§12) ---------------------------------------------------------------------


def test_recommendation_can_only_attach_to_a_confirmed_pattern():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    with pytest.raises(ValueError):
        flow.attach_recommendation(
            organization_id=ORG_ID,
            user_id=USER_ID,
            pattern=surfacing.pattern,  # still PENDING_CONFIRMATION, not CONFIRMED
            recommendation=GrowthRecommendation(statement="x", responds_to=surfacing.pattern.possible_hypotheses[0]),
        )


def test_recommendation_references_the_evidence_backed_hypothesis():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    confirmed = flow.respond(organization_id=ORG_ID, user_id=USER_ID, pattern=surfacing.pattern, response=UserPatternResponse.CONFIRM)
    hypothesis = confirmed.possible_hypotheses[0]
    recommendation = GrowthRecommendation(statement="Add a buffer.", responds_to=hypothesis)
    result = flow.attach_recommendation(organization_id=ORG_ID, user_id=USER_ID, pattern=confirmed, recommendation=recommendation)
    assert result.recommendation.responds_to is hypothesis
    assert hypothesis.explains.supporting_facts  # ultimately grounded in ObservedFacts, not a bare claim


def test_recommendation_is_kept_structurally_separate_from_observed_facts():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    confirmed = flow.respond(organization_id=ORG_ID, user_id=USER_ID, pattern=surfacing.pattern, response=UserPatternResponse.CONFIRM)
    recommendation = GrowthRecommendation(statement="Add a buffer.", responds_to=confirmed.possible_hypotheses[0])
    result = flow.attach_recommendation(organization_id=ORG_ID, user_id=USER_ID, pattern=confirmed, recommendation=recommendation)
    assert result.recommendation.statement not in [fact.statement for fact in result.observed_facts]


# --- experimental learning (§13) --------------------------------------------------------------------


def test_experiments_are_never_created_automatically():
    """Nothing in respond()/attach_recommendation() ever produces an
    Experiment - propose_experiment() must always be an explicit,
    separate call."""
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    confirmed = flow.respond(organization_id=ORG_ID, user_id=USER_ID, pattern=surfacing.pattern, response=UserPatternResponse.CONFIRM)
    recommendation = GrowthRecommendation(statement="Add a buffer.", responds_to=confirmed.possible_hypotheses[0])
    result = flow.attach_recommendation(organization_id=ORG_ID, user_id=USER_ID, pattern=confirmed, recommendation=recommendation)
    assert not hasattr(result, "experiment")


def test_experiment_requires_a_confirmed_pattern_with_a_recommendation():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    confirmed = flow.respond(organization_id=ORG_ID, user_id=USER_ID, pattern=surfacing.pattern, response=UserPatternResponse.CONFIRM)
    with pytest.raises(ValueError):
        flow.propose_experiment(
            confirmed,  # no recommendation attached yet
            organization_id=ORG_ID,
            user_id=USER_ID,
            hypothesis_statement="x",
            adjustment="y",
            measurement_plan="z",
            metric="postponement_count",
            category="learning",
            baseline_window=EvidenceWindow(start=date(2026, 7, 1), end=date(2026, 7, 14)),
            started_on=date(2026, 7, 16),
        )


def test_experiment_can_be_created_from_a_recommendation():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    confirmed = flow.respond(organization_id=ORG_ID, user_id=USER_ID, pattern=surfacing.pattern, response=UserPatternResponse.CONFIRM)
    recommendation = GrowthRecommendation(statement="Add a buffer.", responds_to=confirmed.possible_hypotheses[0])
    with_recommendation = flow.attach_recommendation(organization_id=ORG_ID, user_id=USER_ID, pattern=confirmed, recommendation=recommendation)
    experiment = flow.propose_experiment(
        with_recommendation,
        organization_id=ORG_ID,
        user_id=USER_ID,
        hypothesis_statement="A buffer reduces postponement.",
        adjustment="Add a buffer.",
        measurement_plan="Remeasure in 14 days.",
        metric="postponement_count",
        category="learning",
        baseline_window=EvidenceWindow(start=date(2026, 7, 1), end=date(2026, 7, 14)),
        started_on=date(2026, 7, 16),
    )
    assert experiment.pattern_id == with_recommendation.pattern_id


# --- safety of personal inference (§16) ---------------------------------------------------------------

_FORBIDDEN_DIAGNOSTIC_TERMS = (
    "personality",
    "your character",
    "you are lazy",
    "procrastinat",
    "mental health",
    "disorder",
    "you are the kind of person",
)


def test_pattern_statements_never_use_diagnostic_language():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    lowered = surfacing.pattern.pattern_statement.lower()
    for term in _FORBIDDEN_DIAGNOSTIC_TERMS:
        assert term not in lowered


def test_hypothesis_statements_never_use_diagnostic_language():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    for hypothesis in surfacing.pattern.possible_hypotheses:
        lowered = hypothesis.statement.lower()
        for term in _FORBIDDEN_DIAGNOSTIC_TERMS:
            assert term not in lowered


def test_narration_asks_rather_than_asserts_the_hypothesis():
    flow, intent_repo, evening_repo, pattern_repo = _flow()
    surfacing = _detect_and_surface(flow, intent_repo, evening_repo, pattern_repo)
    assert "Does that seem accurate to you?" in surfacing.narrative
