"""AdaptationFlow (P7.10): the governed Learn/Unlearn/Relearn lifecycle -
evidence gate, duplicate-proposal idempotency, the approval boundary,
adoption/rollback/supersession, scope isolation, and the safety
guarantee that rejected proposals never alter active behavior."""

from datetime import date

import pytest

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.runtime.types import RuntimeResponse
from app.services.personal_os.adaptation import AdaptationEffect, AdaptationTarget
from app.services.personal_os.adaptation_flow import AdaptationFlow
from app.services.personal_os.adaptation_repository import InMemoryAdaptationRepository
from app.services.personal_os.experiment import Experiment, ExperimentBaseline, ExperimentComparison, ExperimentMeasurement
from app.services.personal_os.pattern import Pattern, PatternEvidenceItem
from app.services.personal_os.reasoning import GrowthRecommendation, Hypothesis, InferredPattern, ObservedFact
from app.services.personal_os.shared.types import (
    AdaptationEffectKind,
    AdaptationScope,
    AdaptationStatus,
    Confidence,
    ExperimentOutcome,
    ExperimentStatus,
    LifeDomain,
    PatternStatus,
    PatternType,
    PriorityDirection,
)

ORG_ID, USER_ID = 1, 12


class _FakeRuntime:
    def __init__(self):
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return RuntimeResponse(success=False)


def _flow():
    repo = InMemoryAdaptationRepository()
    flow = AdaptationFlow(repo, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()))
    return flow, repo


def _pattern(pattern_id="p1", status=PatternStatus.CONFIRMED, with_recommendation=True, confidence=Confidence.MEDIUM):
    facts = (ObservedFact(statement="fact one"), ObservedFact(statement="fact two"))
    inferred = InferredPattern(statement="a recurring pattern", supporting_facts=facts)
    hypothesis = Hypothesis(statement="estimates may be optimistic", explains=inferred)
    recommendation = GrowthRecommendation(statement="Add a 50% buffer.", responds_to=hypothesis) if with_recommendation else None
    return Pattern(
        pattern_id=pattern_id,
        pattern_type=PatternType.REPEATED_POSTPONEMENT,
        observation_window_start=date(2026, 7, 1),
        observation_window_end=date(2026, 7, 14),
        evidence=(PatternEvidenceItem(observation_date=date(2026, 7, 1), activity_description="x", activity_category="learning", status="postponed"),),
        observed_facts=facts,
        pattern_statement="4 activities postponed",
        confidence=confidence,
        possible_hypotheses=(hypothesis,),
        recommendation=recommendation,
        status=status,
    )


def _target(scope=AdaptationScope.USER_PREFERENCE, target_id=str(USER_ID)):
    return AdaptationTarget(scope=scope, target_id=target_id)


# --- evidence gate (§6, Evidence Requirement) --------------------------------------------------------


def test_propose_requires_a_confirmed_pattern():
    flow, _ = _flow()
    pending = _pattern(status=PatternStatus.PENDING_CONFIRMATION)
    with pytest.raises(ValueError):
        flow.propose(pending, organization_id=ORG_ID, user_id=USER_ID, target=_target())


def test_propose_requires_an_attached_recommendation():
    flow, _ = _flow()
    confirmed_no_rec = _pattern(with_recommendation=False)
    with pytest.raises(ValueError):
        flow.propose(confirmed_no_rec, organization_id=ORG_ID, user_id=USER_ID, target=_target())


def test_propose_succeeds_with_confirmed_pattern_and_recommendation():
    flow, _ = _flow()
    pattern = _pattern()
    adaptation = flow.propose(pattern, organization_id=ORG_ID, user_id=USER_ID, target=_target())
    assert adaptation.status == AdaptationStatus.PROPOSED
    assert adaptation.pattern_id == "p1"
    assert adaptation.confidence == Confidence.MEDIUM


def test_propose_snapshots_the_patterns_own_confidence():
    flow, _ = _flow()
    pattern = _pattern(confidence=Confidence.HIGH)
    adaptation = flow.propose(pattern, organization_id=ORG_ID, user_id=USER_ID, target=_target())
    assert adaptation.confidence == Confidence.HIGH


# --- duplicate proposals (§16) -----------------------------------------------------------------------


def test_duplicate_proposal_for_the_same_pattern_and_target_is_idempotent():
    flow, _ = _flow()
    pattern = _pattern()
    first = flow.propose(pattern, organization_id=ORG_ID, user_id=USER_ID, target=_target())
    second = flow.propose(pattern, organization_id=ORG_ID, user_id=USER_ID, target=_target())
    assert first.adaptation_id == second.adaptation_id


def test_proposal_for_the_same_pattern_but_a_different_target_is_not_a_duplicate():
    flow, _ = _flow()
    pattern = _pattern()
    first = flow.propose(pattern, organization_id=ORG_ID, user_id=USER_ID, target=_target(target_id="1"))
    second = flow.propose(pattern, organization_id=ORG_ID, user_id=USER_ID, target=_target(target_id="2"))
    assert first.adaptation_id != second.adaptation_id


# --- lifecycle transitions (§5) -----------------------------------------------------------------------


def test_begin_evaluation_transitions_from_proposed():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    under_eval = flow.begin_evaluation(proposed, organization_id=ORG_ID, user_id=USER_ID)
    assert under_eval.status == AdaptationStatus.UNDER_EVALUATION


def test_begin_evaluation_rejects_invalid_source_status():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    approved = flow.approve(proposed, organization_id=ORG_ID, user_id=USER_ID)
    with pytest.raises(ValueError):
        flow.begin_evaluation(approved, organization_id=ORG_ID, user_id=USER_ID)


def test_approve_is_callable_directly_from_proposed():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    approved = flow.approve(proposed, organization_id=ORG_ID, user_id=USER_ID, reason="looks safe")
    assert approved.status == AdaptationStatus.APPROVED
    assert approved.decision_reason == "looks safe"


def test_approve_is_callable_from_under_evaluation():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    under_eval = flow.begin_evaluation(proposed, organization_id=ORG_ID, user_id=USER_ID)
    approved = flow.approve(under_eval, organization_id=ORG_ID, user_id=USER_ID)
    assert approved.status == AdaptationStatus.APPROVED


def test_adopt_requires_approved():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    with pytest.raises(ValueError):
        flow.adopt(proposed, organization_id=ORG_ID, user_id=USER_ID)


def test_adopt_succeeds_from_approved():
    flow, repo = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    approved = flow.approve(proposed, organization_id=ORG_ID, user_id=USER_ID)
    adopted = flow.adopt(approved, organization_id=ORG_ID, user_id=USER_ID)
    assert adopted.status == AdaptationStatus.ADOPTED
    assert flow.get_adopted(organization_id=ORG_ID, user_id=USER_ID, target=_target()).adaptation_id == adopted.adaptation_id


# --- approval boundary / rejection never alters active behavior (§4, §12) ------------------------------


def test_reject_requires_a_reason():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    with pytest.raises(ValueError):
        flow.reject(proposed, organization_id=ORG_ID, user_id=USER_ID, reason="")


def test_rejected_proposal_never_becomes_adopted():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    rejected = flow.reject(proposed, organization_id=ORG_ID, user_id=USER_ID, reason="not worth the risk")
    assert rejected.status == AdaptationStatus.REJECTED
    assert flow.get_adopted(organization_id=ORG_ID, user_id=USER_ID, target=_target()) is None


def test_rejected_proposal_cannot_later_be_adopted():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    rejected = flow.reject(proposed, organization_id=ORG_ID, user_id=USER_ID, reason="no")
    with pytest.raises(ValueError):
        flow.adopt(rejected, organization_id=ORG_ID, user_id=USER_ID)


def test_cannot_reject_an_already_adopted_adaptation():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    approved = flow.approve(proposed, organization_id=ORG_ID, user_id=USER_ID)
    adopted = flow.adopt(approved, organization_id=ORG_ID, user_id=USER_ID)
    with pytest.raises(ValueError):
        flow.reject(adopted, organization_id=ORG_ID, user_id=USER_ID, reason="too late")


# --- rollback / retire (UNLEARN, §7, §13) ---------------------------------------------------------------


def test_rollback_requires_adopted():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    with pytest.raises(ValueError):
        flow.rollback(proposed, organization_id=ORG_ID, user_id=USER_ID, reason="x")


def test_rollback_requires_a_reason():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    approved = flow.approve(proposed, organization_id=ORG_ID, user_id=USER_ID)
    adopted = flow.adopt(approved, organization_id=ORG_ID, user_id=USER_ID)
    with pytest.raises(ValueError):
        flow.rollback(adopted, organization_id=ORG_ID, user_id=USER_ID, reason="")


def test_rollback_transitions_to_rolled_back_and_clears_adopted():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    approved = flow.approve(proposed, organization_id=ORG_ID, user_id=USER_ID)
    adopted = flow.adopt(approved, organization_id=ORG_ID, user_id=USER_ID)
    rolled_back = flow.rollback(adopted, organization_id=ORG_ID, user_id=USER_ID, reason="caused confusion")
    assert rolled_back.status == AdaptationStatus.ROLLED_BACK
    assert flow.get_adopted(organization_id=ORG_ID, user_id=USER_ID, target=_target()) is None


def test_retire_is_pure_unlearn_with_no_replacement():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    approved = flow.approve(proposed, organization_id=ORG_ID, user_id=USER_ID)
    adopted = flow.adopt(approved, organization_id=ORG_ID, user_id=USER_ID)
    retired = flow.retire(adopted, organization_id=ORG_ID, user_id=USER_ID, reason="no longer relevant")
    assert retired.status == AdaptationStatus.SUPERSEDED
    assert retired.supersedes_adaptation_id is None
    assert flow.get_adopted(organization_id=ORG_ID, user_id=USER_ID, target=_target()) is None


def test_retire_preserves_the_historical_record():
    """§7: unlearning must not destroy historical evidence."""
    flow, repo = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    approved = flow.approve(proposed, organization_id=ORG_ID, user_id=USER_ID)
    adopted = flow.adopt(approved, organization_id=ORG_ID, user_id=USER_ID)
    flow.retire(adopted, organization_id=ORG_ID, user_id=USER_ID, reason="obsolete")

    history = repo.get_history(organization_id=ORG_ID, user_id=USER_ID, adaptation_id=adopted.adaptation_id)
    assert [h.status for h in history] == [
        AdaptationStatus.PROPOSED, AdaptationStatus.APPROVED, AdaptationStatus.ADOPTED, AdaptationStatus.SUPERSEDED,
    ]
    assert history[0].pattern_id == "p1"  # the original evidence link is never rewritten


# --- RELEARN: lineage preserved, predecessor superseded on adoption (§8) -------------------------------


def test_relearn_requires_superseding_an_adopted_adaptation():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(pattern_id="p1"), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    with pytest.raises(ValueError):
        flow.propose_relearn(_pattern(pattern_id="p2"), organization_id=ORG_ID, user_id=USER_ID, supersedes=proposed)


def test_relearn_lineage_is_recorded_at_proposal_time():
    flow, _ = _flow()
    original = flow.propose(_pattern(pattern_id="p1"), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    adopted_original = flow.adopt(flow.approve(original, organization_id=ORG_ID, user_id=USER_ID), organization_id=ORG_ID, user_id=USER_ID)

    relearned = flow.propose_relearn(_pattern(pattern_id="p2"), organization_id=ORG_ID, user_id=USER_ID, supersedes=adopted_original)
    assert relearned.supersedes_adaptation_id == adopted_original.adaptation_id


def test_relearn_supersedes_the_predecessor_only_once_the_replacement_is_adopted():
    flow, repo = _flow()
    original = flow.propose(_pattern(pattern_id="p1"), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    adopted_original = flow.adopt(flow.approve(original, organization_id=ORG_ID, user_id=USER_ID), organization_id=ORG_ID, user_id=USER_ID)

    relearn_proposal = flow.propose_relearn(_pattern(pattern_id="p2"), organization_id=ORG_ID, user_id=USER_ID, supersedes=adopted_original)
    # predecessor still ADOPTED - a mere proposal must not retroactively change it
    assert repo.get_latest(organization_id=ORG_ID, user_id=USER_ID, adaptation_id=adopted_original.adaptation_id).status == AdaptationStatus.ADOPTED

    relearn_approved = flow.approve(relearn_proposal, organization_id=ORG_ID, user_id=USER_ID)
    flow.adopt(relearn_approved, organization_id=ORG_ID, user_id=USER_ID)

    predecessor_now = repo.get_latest(organization_id=ORG_ID, user_id=USER_ID, adaptation_id=adopted_original.adaptation_id)
    assert predecessor_now.status == AdaptationStatus.SUPERSEDED


def test_relearn_leaves_exactly_one_adopted_adaptation_for_the_target():
    flow, _ = _flow()
    original = flow.propose(_pattern(pattern_id="p1"), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    adopted_original = flow.adopt(flow.approve(original, organization_id=ORG_ID, user_id=USER_ID), organization_id=ORG_ID, user_id=USER_ID)
    relearn_proposal = flow.propose_relearn(_pattern(pattern_id="p2"), organization_id=ORG_ID, user_id=USER_ID, supersedes=adopted_original)
    relearn_adopted = flow.adopt(flow.approve(relearn_proposal, organization_id=ORG_ID, user_id=USER_ID), organization_id=ORG_ID, user_id=USER_ID)

    current = flow.get_adopted(organization_id=ORG_ID, user_id=USER_ID, target=_target())
    assert current.adaptation_id == relearn_adopted.adaptation_id


# --- scope isolation (§9) ---------------------------------------------------------------------------------


def test_mission_adaptation_stays_scoped_to_its_own_mission():
    flow, _ = _flow()
    mission_a = _target(scope=AdaptationScope.MISSION, target_id="mission-a")
    mission_b = _target(scope=AdaptationScope.MISSION, target_id="mission-b")
    proposed = flow.propose(_pattern(pattern_id="p1"), organization_id=ORG_ID, user_id=USER_ID, target=mission_a)
    flow.adopt(flow.approve(proposed, organization_id=ORG_ID, user_id=USER_ID), organization_id=ORG_ID, user_id=USER_ID)

    assert flow.get_adopted(organization_id=ORG_ID, user_id=USER_ID, target=mission_a) is not None
    assert flow.get_adopted(organization_id=ORG_ID, user_id=USER_ID, target=mission_b) is None


def test_user_preference_does_not_leak_across_users():
    flow, repo = _flow()
    proposed = flow.propose(_pattern(pattern_id="p1"), organization_id=ORG_ID, user_id=USER_ID, target=_target(AdaptationScope.USER_PREFERENCE, "1"))
    flow.adopt(flow.approve(proposed, organization_id=ORG_ID, user_id=USER_ID), organization_id=ORG_ID, user_id=USER_ID)

    other_user_flow = AdaptationFlow(repo)
    assert other_user_flow.get_adopted(organization_id=ORG_ID, user_id=999, target=_target(AdaptationScope.USER_PREFERENCE, "1")) is None


def test_workflow_adaptation_remains_workflow_scoped():
    flow, _ = _flow()
    workflow_a = _target(scope=AdaptationScope.WORKFLOW, target_id="morning-planning")
    workflow_b = _target(scope=AdaptationScope.WORKFLOW, target_id="evening-reflection")
    proposed = flow.propose(_pattern(pattern_id="p1"), organization_id=ORG_ID, user_id=USER_ID, target=workflow_a)
    flow.adopt(flow.approve(proposed, organization_id=ORG_ID, user_id=USER_ID), organization_id=ORG_ID, user_id=USER_ID)

    assert flow.get_adopted(organization_id=ORG_ID, user_id=USER_ID, target=workflow_a) is not None
    assert flow.get_adopted(organization_id=ORG_ID, user_id=USER_ID, target=workflow_b) is None


# --- measurement linking (§14) ------------------------------------------------------------------------


def _experiment(pattern_id="p1", status=ExperimentStatus.PROPOSED, comparison=None):
    baseline = ExperimentBaseline(metric="postponement_count", category="learning", period_start=date(2026, 7, 1), period_end=date(2026, 7, 14), value=4.0, observation_count=4)
    return Experiment(
        experiment_id="e1", pattern_id=pattern_id, hypothesis_statement="h", adjustment="Add a buffer", measurement_plan="m",
        baseline=baseline, started_on=date(2026, 7, 16), status=status, comparison=comparison,
    )


def test_link_experiment_requires_under_evaluation():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(pattern_id="p1"), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    with pytest.raises(ValueError):
        flow.link_experiment(proposed, organization_id=ORG_ID, user_id=USER_ID, experiment=_experiment())


def test_link_experiment_requires_matching_pattern():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(pattern_id="p1"), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    under_eval = flow.begin_evaluation(proposed, organization_id=ORG_ID, user_id=USER_ID)
    with pytest.raises(ValueError):
        flow.link_experiment(under_eval, organization_id=ORG_ID, user_id=USER_ID, experiment=_experiment(pattern_id="different-pattern"))


def test_link_experiment_stores_the_reference_only():
    flow, _ = _flow()
    proposed = flow.propose(_pattern(pattern_id="p1"), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    under_eval = flow.begin_evaluation(proposed, organization_id=ORG_ID, user_id=USER_ID)
    linked = flow.link_experiment(under_eval, organization_id=ORG_ID, user_id=USER_ID, experiment=_experiment())
    assert linked.experiment_id == "e1"


def test_measured_outcome_reads_through_to_the_linked_experiment():
    baseline = ExperimentBaseline(metric="postponement_count", category="learning", period_start=date(2026, 7, 1), period_end=date(2026, 7, 14), value=4.0, observation_count=4)
    measurement = ExperimentMeasurement(metric="postponement_count", category="learning", period_start=date(2026, 7, 16), period_end=date(2026, 7, 30), value=1.0, observation_count=4)
    comparison = ExperimentComparison(baseline=baseline, measurement=measurement, absolute_change=-3.0, relative_change=-0.75, outcome=ExperimentOutcome.IMPROVED, confidence=Confidence.MEDIUM, observation_statement="Postponements decreased.")
    experiment = _experiment(comparison=comparison)
    assert AdaptationFlow.measured_outcome(experiment) == ExperimentOutcome.IMPROVED


def test_measured_outcome_is_none_when_no_experiment_linked():
    assert AdaptationFlow.measured_outcome(None) is None


def test_adoption_is_never_automatic_from_a_measured_outcome():
    """§14: adoption is never automatic - even a linked, IMPROVED
    experiment does not adopt anything by itself; approve()/adopt() are
    always separate, explicit calls."""
    flow, _ = _flow()
    proposed = flow.propose(_pattern(pattern_id="p1"), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    under_eval = flow.begin_evaluation(proposed, organization_id=ORG_ID, user_id=USER_ID)
    linked = flow.link_experiment(under_eval, organization_id=ORG_ID, user_id=USER_ID, experiment=_experiment())
    # linking a (still-unmeasured) experiment must never itself change status
    assert linked.status == AdaptationStatus.UNDER_EVALUATION


# --- narration ------------------------------------------------------------------------------------------


def test_present_falls_back_to_deterministic_phrasing_when_the_runtime_fails():
    flow, _ = _flow()
    pattern = _pattern()
    proposed = flow.propose(pattern, organization_id=ORG_ID, user_id=USER_ID, target=_target())
    narrative = flow.present(proposed, pattern, organization_id=ORG_ID)
    assert "Add a 50% buffer." in narrative


# --- runtime effect (P7.11): explicit, structured, never inferred from PatternType -----------------------


def test_propose_without_an_effect_produces_a_purely_advisory_adaptation():
    """Unchanged P7.10 behavior - omitting `effect` (every existing
    caller) must not gain a runtime-consumable effect from nowhere."""
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target())
    assert proposed.effect is None


def test_propose_accepts_an_explicit_structured_effect():
    effect = AdaptationEffect(kind=AdaptationEffectKind.PRIORITY_ADJUSTMENT, direction=PriorityDirection.BOOST)
    flow, _ = _flow()
    proposed = flow.propose(
        _pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target(AdaptationScope.USER_PREFERENCE, LifeDomain.CAREER.value), effect=effect
    )
    assert proposed.effect == effect


def test_user_preference_priority_adjustment_requires_a_life_domain_target_id():
    """§9's own STOP-rather-than-guess rule: a USER_PREFERENCE
    PRIORITY_ADJUSTMENT effect has exactly one stable, structured
    identifier to match against Priority candidates (LifeDomain) - an
    arbitrary target_id string is rejected at construction, never
    silently accepted and later fuzzy-matched."""
    effect = AdaptationEffect(kind=AdaptationEffectKind.PRIORITY_ADJUSTMENT, direction=PriorityDirection.BOOST)
    flow, _ = _flow()
    with pytest.raises(ValueError):
        flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target(AdaptationScope.USER_PREFERENCE, "not-a-domain"), effect=effect)


def test_mission_priority_adjustment_does_not_require_a_life_domain_target_id():
    """A MISSION target's own mission_id is already the stable,
    structured identifier - no additional constraint is needed there."""
    effect = AdaptationEffect(kind=AdaptationEffectKind.PRIORITY_ADJUSTMENT, direction=PriorityDirection.SUPPRESS)
    flow, _ = _flow()
    proposed = flow.propose(_pattern(), organization_id=ORG_ID, user_id=USER_ID, target=_target(AdaptationScope.MISSION, "mission-1"), effect=effect)
    assert proposed.effect == effect


def test_relearn_can_carry_a_new_effect_replacing_the_predecessors():
    domain_target = _target(AdaptationScope.USER_PREFERENCE, LifeDomain.CAREER.value)
    boost = AdaptationEffect(kind=AdaptationEffectKind.PRIORITY_ADJUSTMENT, direction=PriorityDirection.BOOST)
    suppress = AdaptationEffect(kind=AdaptationEffectKind.PRIORITY_ADJUSTMENT, direction=PriorityDirection.SUPPRESS)
    flow, _ = _flow()

    first = flow.propose(_pattern(pattern_id="p1"), organization_id=ORG_ID, user_id=USER_ID, target=domain_target, effect=boost)
    first = flow.approve(first, organization_id=ORG_ID, user_id=USER_ID)
    first = flow.adopt(first, organization_id=ORG_ID, user_id=USER_ID)

    second = flow.propose_relearn(_pattern(pattern_id="p2"), organization_id=ORG_ID, user_id=USER_ID, supersedes=first, effect=suppress)
    second = flow.approve(second, organization_id=ORG_ID, user_id=USER_ID)
    second = flow.adopt(second, organization_id=ORG_ID, user_id=USER_ID)

    assert flow.get_adopted(organization_id=ORG_ID, user_id=USER_ID, target=domain_target).effect == suppress
