"""AdaptationOutcomeFlow (P7.12): the orchestration that closes the loop
P7.11 left open at "behavior changed" - a real pre-adoption baseline, a
real post-adoption measurement (never leaking evidence across the
adoption-day boundary), the EXISTING Experiment comparison/review doing
all the actual measurement math, and a plain, non-binding recommendation
that never decides KEEP/MODIFY/ROLLBACK/CONTINUE on the user's behalf."""

from datetime import UTC, date, datetime

import pytest

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.runtime.types import RuntimeResponse
from app.services.personal_os.adaptation import Adaptation, AdaptationTarget
from app.services.personal_os.adaptation_flow import AdaptationFlow
from app.services.personal_os.adaptation_outcome_flow import AdaptationOutcomeFlow
from app.services.personal_os.adaptation_repository import InMemoryAdaptationRepository
from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.evening import EveningReflection, InMemoryEveningReflectionRepository
from app.services.personal_os.experiment_flow import ExperimentFlow
from app.services.personal_os.experiment_repository import InMemoryExperimentRepository
from app.services.personal_os.pattern import Pattern, PatternEvidenceItem
from app.services.personal_os.pattern_evidence import EvidenceWindow
from app.services.personal_os.pattern_flow import PatternDetectionFlow
from app.services.personal_os.pattern_repository import InMemoryPatternRepository
from app.services.personal_os.reasoning import GrowthRecommendation, Hypothesis, InferredPattern, ObservedFact
from app.services.personal_os.reconciliation import ReconciliationEvidence, reconcile_all
from app.services.personal_os.repository import InMemoryDailyIntentRepository
from app.services.personal_os.shared.types import AdaptationScope, AdaptationStatus, Confidence, DayType, ExperimentOutcome, PatternStatus, PatternType

ORG_ID, USER_ID = 1, 30
ADOPTED_AT = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


class _FakeRuntime:
    def __init__(self):
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return RuntimeResponse(success=False)


def _pattern(pattern_id="p1"):
    facts = (ObservedFact(statement="fact one"), ObservedFact(statement="fact two"))
    inferred = InferredPattern(statement="a recurring pattern", supporting_facts=facts)
    hypothesis = Hypothesis(statement="learning work is deprioritized", explains=inferred)
    recommendation = GrowthRecommendation(statement="Prioritize learning work earlier in the day.", responds_to=hypothesis)
    return Pattern(
        pattern_id=pattern_id,
        pattern_type=PatternType.REPEATED_POSTPONEMENT,
        observation_window_start=date(2026, 7, 1),
        observation_window_end=date(2026, 7, 14),
        evidence=(PatternEvidenceItem(observation_date=date(2026, 7, 1), activity_description="x", activity_category="learning", status="postponed"),),
        observed_facts=facts,
        pattern_statement="Learning work was postponed repeatedly",
        confidence=Confidence.MEDIUM,
        possible_hypotheses=(hypothesis,),
        recommendation=recommendation,
        status=PatternStatus.CONFIRMED,
    )


def _target():
    return AdaptationTarget(scope=AdaptationScope.USER_PREFERENCE, target_id=str(USER_ID))


def _seed_adopted(adaptation_repo, *, pattern_id="p1", adopted_at=ADOPTED_AT):
    adaptation = Adaptation(adaptation_id="", target=_target(), pattern_id=pattern_id, confidence=Confidence.MEDIUM, status=AdaptationStatus.ADOPTED, updated_at=adopted_at)
    return adaptation_repo.save(adaptation, organization_id=ORG_ID, user_id=USER_ID)


def _seed_day(intent_repo, evening_repo, day, *, description, completed=False, postponed=False):
    activity = PlannedActivity(description=description, focus_area="learning")
    intent = DailyIntent(intent_date=day, stated_intention="Study", day_type=DayType.STUDY, planned_activities=(activity,))
    intent_repo.save(intent, organization_id=ORG_ID, user_id=USER_ID)
    evidence = {description: ReconciliationEvidence(explicitly_completed=completed, explicitly_postponed=postponed)}
    reconciliations = reconcile_all((activity,), evidence)
    reflection = EveningReflection(reflection_date=day, accomplishments=(), evidence_by_activity_description=evidence)
    evening_repo.save(reflection, reconciliations, organization_id=ORG_ID, user_id=USER_ID, daily_intent_id=intent.intent_id)


def _flow():
    intent_repo = InMemoryDailyIntentRepository()
    evening_repo = InMemoryEveningReflectionRepository()
    pattern_repo = InMemoryPatternRepository()
    experiment_repo = InMemoryExperimentRepository()
    adaptation_repo = InMemoryAdaptationRepository()

    pattern_flow = PatternDetectionFlow(intent_repo, evening_repo, pattern_repo, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()), experiment_repository=experiment_repo)
    experiment_flow = ExperimentFlow(intent_repo, evening_repo, experiment_repo, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()))
    adaptation_flow = AdaptationFlow(adaptation_repo, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()))
    outcome_flow = AdaptationOutcomeFlow(adaptation_repo, adaptation_flow, pattern_flow, experiment_flow, experiment_repo)

    return outcome_flow, adaptation_repo, experiment_repo, intent_repo, evening_repo


def _seed_baseline_evidence(intent_repo, evening_repo):
    """4 postponements across the pre-adoption window - the exact same
    P4 worked example's own baseline shape (postponement_count=4)."""
    for day in (date(2026, 7, 1), date(2026, 7, 3), date(2026, 7, 6), date(2026, 7, 10)):
        _seed_day(intent_repo, evening_repo, day, description="Study transformers", postponed=True)


def _seed_improved_post_adoption_evidence(intent_repo, evening_repo):
    """3 completions, 1 postponement after adoption - a genuine,
    75%-relative-decrease improvement, matching P4's own worked example."""
    _seed_day(intent_repo, evening_repo, date(2026, 7, 16), description="Study transformers", completed=True)
    _seed_day(intent_repo, evening_repo, date(2026, 7, 18), description="Study transformers", completed=True)
    _seed_day(intent_repo, evening_repo, date(2026, 7, 20), description="Study transformers", postponed=True)
    _seed_day(intent_repo, evening_repo, date(2026, 7, 22), description="Study transformers", completed=True)


# --- propose_outcome_experiment: baseline correctness (§6) -------------------------------------------


def test_propose_outcome_experiment_requires_adopted():
    outcome_flow, adaptation_repo, *_ = _flow()
    proposed = Adaptation(adaptation_id="a1", target=_target(), pattern_id="p1", confidence=Confidence.MEDIUM, status=AdaptationStatus.PROPOSED)
    adaptation_repo.save(proposed, organization_id=ORG_ID, user_id=USER_ID)
    with pytest.raises(ValueError):
        outcome_flow.propose_outcome_experiment(
            proposed, organization_id=ORG_ID, user_id=USER_ID, pattern=_pattern(), hypothesis_statement="h", adjustment="a", measurement_plan="m",
            metric="postponement_count", category="learning", baseline_window=EvidenceWindow(date(2026, 7, 1), date(2026, 7, 14)),
        )


def test_propose_outcome_experiment_requires_matching_pattern():
    outcome_flow, adaptation_repo, *_ = _flow()
    adopted = _seed_adopted(adaptation_repo, pattern_id="p1")
    with pytest.raises(ValueError):
        outcome_flow.propose_outcome_experiment(
            adopted, organization_id=ORG_ID, user_id=USER_ID, pattern=_pattern(pattern_id="different"), hypothesis_statement="h", adjustment="a",
            measurement_plan="m", metric="postponement_count", category="learning", baseline_window=EvidenceWindow(date(2026, 7, 1), date(2026, 7, 14)),
        )


def test_propose_outcome_experiment_rejects_a_baseline_window_reaching_into_post_adoption():
    outcome_flow, adaptation_repo, _, intent_repo, evening_repo = _flow()
    _seed_baseline_evidence(intent_repo, evening_repo)
    adopted = _seed_adopted(adaptation_repo, pattern_id="p1")
    with pytest.raises(ValueError):
        outcome_flow.propose_outcome_experiment(
            adopted, organization_id=ORG_ID, user_id=USER_ID, pattern=_pattern(), hypothesis_statement="h", adjustment="a", measurement_plan="m",
            metric="postponement_count", category="learning", baseline_window=EvidenceWindow(date(2026, 7, 1), date(2026, 7, 16)),  # reaches into started_on
        )


def test_propose_outcome_experiment_rejects_no_pre_adoption_evidence():
    """§6: never fabricate a baseline from nothing - delegated entirely
    to the EXISTING propose_experiment()/build_baseline() refusal, not a
    new code path."""
    outcome_flow, adaptation_repo, *_ = _flow()
    adopted = _seed_adopted(adaptation_repo, pattern_id="p1")
    with pytest.raises(ValueError):
        outcome_flow.propose_outcome_experiment(
            adopted, organization_id=ORG_ID, user_id=USER_ID, pattern=_pattern(), hypothesis_statement="h", adjustment="a", measurement_plan="m",
            metric="postponement_count", category="learning", baseline_window=EvidenceWindow(date(2026, 7, 1), date(2026, 7, 14)),
        )


def test_propose_outcome_experiment_computes_started_on_from_the_adoption_boundary():
    outcome_flow, adaptation_repo, experiment_repo, intent_repo, evening_repo = _flow()
    _seed_baseline_evidence(intent_repo, evening_repo)
    adopted = _seed_adopted(adaptation_repo, pattern_id="p1")

    linked = outcome_flow.propose_outcome_experiment(
        adopted, organization_id=ORG_ID, user_id=USER_ID, pattern=_pattern(), hypothesis_statement="h", adjustment="Prioritize learning earlier",
        measurement_plan="m", metric="postponement_count", category="learning", baseline_window=EvidenceWindow(date(2026, 7, 1), date(2026, 7, 14)),
    )

    assert linked.outcome_experiment_id is not None
    experiment = experiment_repo.get_latest(organization_id=ORG_ID, user_id=USER_ID, experiment_id=linked.outcome_experiment_id)
    assert experiment.started_on == date(2026, 7, 16)  # the day AFTER adoption (2026-07-15), never the adoption day itself
    assert experiment.baseline.value == 4.0
    assert experiment.baseline.observation_count == 4


# --- review_outcome: post-adoption slicing, causality-safe comparison (§7-§9) -------------------------


def _propose_and_review(outcome_flow, adaptation_repo, intent_repo, evening_repo, *, today=date(2026, 7, 30)):
    adopted = _seed_adopted(adaptation_repo, pattern_id="p1")
    linked = outcome_flow.propose_outcome_experiment(
        adopted, organization_id=ORG_ID, user_id=USER_ID, pattern=_pattern(), hypothesis_statement="h", adjustment="Prioritize learning earlier",
        measurement_plan="m", metric="postponement_count", category="learning", baseline_window=EvidenceWindow(date(2026, 7, 1), date(2026, 7, 14)),
    )
    review = outcome_flow.review_outcome(linked, organization_id=ORG_ID, user_id=USER_ID, today=today)
    return linked, review


def test_review_outcome_excludes_evidence_on_the_adoption_day_itself():
    """§7's own required proof: an observation immediately on the
    adoption day (2026-07-15) must count toward neither the baseline
    (window ends 2026-07-14) nor the measurement (window starts
    2026-07-16)."""
    outcome_flow, adaptation_repo, _, intent_repo, evening_repo = _flow()
    _seed_baseline_evidence(intent_repo, evening_repo)
    _seed_day(intent_repo, evening_repo, date(2026, 7, 15), description="Study transformers", postponed=True)  # adoption day itself
    _seed_improved_post_adoption_evidence(intent_repo, evening_repo)

    _, review = _propose_and_review(outcome_flow, adaptation_repo, intent_repo, evening_repo)

    assert review.experiment.comparison.baseline.observation_count == 4  # not 5
    assert review.experiment.comparison.measurement.observation_count == 4  # not 5


def test_review_outcome_produces_a_causality_safe_improved_comparison():
    outcome_flow, adaptation_repo, _, intent_repo, evening_repo = _flow()
    _seed_baseline_evidence(intent_repo, evening_repo)
    _seed_improved_post_adoption_evidence(intent_repo, evening_repo)

    _, review = _propose_and_review(outcome_flow, adaptation_repo, intent_repo, evening_repo)

    assert review.experiment.comparison.outcome == ExperimentOutcome.IMPROVED
    assert "caused" not in review.experiment.comparison.observation_statement.lower()
    assert review.is_currently_adopted is True
    assert review.adaptation_status == AdaptationStatus.ADOPTED
    assert "causality has not been established" in review.recommendation


def test_review_outcome_insufficient_data_when_nothing_observed_after_adoption():
    outcome_flow, adaptation_repo, _, intent_repo, evening_repo = _flow()
    _seed_baseline_evidence(intent_repo, evening_repo)
    # no post-adoption evidence at all

    _, review = _propose_and_review(outcome_flow, adaptation_repo, intent_repo, evening_repo)

    assert review.experiment.comparison.outcome == ExperimentOutcome.INSUFFICIENT_DATA
    assert "not enough evidence" in review.recommendation.lower()


def test_review_outcome_requires_a_linked_outcome_experiment():
    outcome_flow, adaptation_repo, *_ = _flow()
    adopted = _seed_adopted(adaptation_repo, pattern_id="p1")
    with pytest.raises(ValueError):
        outcome_flow.review_outcome(adopted, organization_id=ORG_ID, user_id=USER_ID, today=date(2026, 7, 30))


def test_review_outcome_raises_when_the_linked_experiment_is_missing():
    outcome_flow, adaptation_repo, *_ = _flow()
    adaptation = Adaptation(
        adaptation_id="", target=_target(), pattern_id="p1", confidence=Confidence.MEDIUM, status=AdaptationStatus.ADOPTED,
        outcome_experiment_id="does-not-exist", updated_at=ADOPTED_AT,
    )
    saved = adaptation_repo.save(adaptation, organization_id=ORG_ID, user_id=USER_ID)
    with pytest.raises(ValueError):
        outcome_flow.review_outcome(saved, organization_id=ORG_ID, user_id=USER_ID, today=date(2026, 7, 30))


# --- adaptation status changes during observation (§14) -----------------------------------------------


def test_review_outcome_flags_a_rolled_back_adaptation_as_no_longer_currently_adopted():
    """The Adaptation is rolled back BEFORE its outcome is ever
    reviewed - the review still runs (the measurement itself is
    preserved, not discarded), but must honestly report the Adaptation
    is no longer active."""
    outcome_flow, adaptation_repo, _, intent_repo, evening_repo = _flow()
    _seed_baseline_evidence(intent_repo, evening_repo)
    _seed_improved_post_adoption_evidence(intent_repo, evening_repo)
    adopted = _seed_adopted(adaptation_repo, pattern_id="p1")
    linked = outcome_flow.propose_outcome_experiment(
        adopted, organization_id=ORG_ID, user_id=USER_ID, pattern=_pattern(), hypothesis_statement="h", adjustment="Prioritize learning earlier",
        measurement_plan="m", metric="postponement_count", category="learning", baseline_window=EvidenceWindow(date(2026, 7, 1), date(2026, 7, 14)),
    )

    adaptation_flow = AdaptationFlow(adaptation_repo)
    adaptation_flow.rollback(linked, organization_id=ORG_ID, user_id=USER_ID, reason="no longer wanted")

    review = outcome_flow.review_outcome(linked, organization_id=ORG_ID, user_id=USER_ID, today=date(2026, 7, 31))

    assert review.is_currently_adopted is False
    assert review.adaptation_status == AdaptationStatus.ROLLED_BACK
    assert "no longer currently adopted" in review.recommendation
    # the measurement itself is preserved, not discarded
    assert review.experiment.comparison.outcome == ExperimentOutcome.IMPROVED


def test_review_outcome_flags_a_superseded_adaptation_as_no_longer_currently_adopted():
    outcome_flow, adaptation_repo, _, intent_repo, evening_repo = _flow()
    _seed_baseline_evidence(intent_repo, evening_repo)
    _seed_improved_post_adoption_evidence(intent_repo, evening_repo)
    adopted = _seed_adopted(adaptation_repo, pattern_id="p1")
    linked = outcome_flow.propose_outcome_experiment(
        adopted, organization_id=ORG_ID, user_id=USER_ID, pattern=_pattern(), hypothesis_statement="h", adjustment="Prioritize learning earlier",
        measurement_plan="m", metric="postponement_count", category="learning", baseline_window=EvidenceWindow(date(2026, 7, 1), date(2026, 7, 14)),
    )

    from dataclasses import replace

    adaptation_repo.save(replace(linked, status=AdaptationStatus.SUPERSEDED), organization_id=ORG_ID, user_id=USER_ID)

    review = outcome_flow.review_outcome(linked, organization_id=ORG_ID, user_id=USER_ID, today=date(2026, 7, 31))

    assert review.is_currently_adopted is False
    assert review.adaptation_status == AdaptationStatus.SUPERSEDED
    assert "no longer currently adopted" in review.recommendation


# --- rollback/relearn remain explicit, human-governed (§11, §12) --------------------------------------


def test_review_outcome_never_itself_calls_rollback_or_propose_relearn():
    """A WORSENED outcome only ever recommends - it never executes a
    consequential action on its own."""
    outcome_flow, adaptation_repo, _, intent_repo, evening_repo = _flow()
    _seed_baseline_evidence(intent_repo, evening_repo)
    # worse: MORE postponements after adoption than before
    for day in (date(2026, 7, 16), date(2026, 7, 17), date(2026, 7, 18), date(2026, 7, 19)):
        _seed_day(intent_repo, evening_repo, day, description="Study transformers", postponed=True)

    linked, review = _propose_and_review(outcome_flow, adaptation_repo, intent_repo, evening_repo)

    assert review.experiment.comparison.outcome in (ExperimentOutcome.WORSENED, ExperimentOutcome.UNCHANGED)
    # the adaptation itself is untouched - still ADOPTED, never auto-rolled-back
    current = adaptation_repo.get_latest(organization_id=ORG_ID, user_id=USER_ID, adaptation_id=linked.adaptation_id)
    assert current.status == AdaptationStatus.ADOPTED


# --- tenant/user isolation ------------------------------------------------------------------------------


def test_outcome_experiment_lookup_is_isolated_per_user():
    outcome_flow, adaptation_repo, experiment_repo, intent_repo, evening_repo = _flow()
    _seed_baseline_evidence(intent_repo, evening_repo)
    adopted = _seed_adopted(adaptation_repo, pattern_id="p1")
    linked = outcome_flow.propose_outcome_experiment(
        adopted, organization_id=ORG_ID, user_id=USER_ID, pattern=_pattern(), hypothesis_statement="h", adjustment="a", measurement_plan="m",
        metric="postponement_count", category="learning", baseline_window=EvidenceWindow(date(2026, 7, 1), date(2026, 7, 14)),
    )

    other_user_id = USER_ID + 1
    assert experiment_repo.get_latest(organization_id=ORG_ID, user_id=other_user_id, experiment_id=linked.outcome_experiment_id) is None
