"""EveningReflectionFlow (P2 §3-§5, §13): begins, completes, distinguishes
every reconciliation status, preserves user explanations, asks only what
is necessary, and never treats rest as failure."""

from datetime import date

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.runtime.types import RuntimeResponse
from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.evening import InMemoryEveningReflectionRepository
from app.services.personal_os.evening_flow import EveningReflectionFlow
from app.services.personal_os.repository import InMemoryDailyIntentRepository
from app.services.personal_os.shared.types import DayType, ReconciliationStatus


class _FakeRuntime:
    def __init__(self, text="Understood."):
        self.text = text
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return RuntimeResponse(success=False)  # exercises the honest fallback path deliberately


def _seed_intent(intent_repo, activities, day_type=DayType.WORK, is_rest_day=False, intent_date=date(2026, 8, 13)):
    intent = DailyIntent(
        intent_date=intent_date,
        stated_intention="x",
        day_type=day_type,
        is_rest_day=is_rest_day,
        planned_activities=activities,
    )
    intent_repo.save(intent, organization_id=1, user_id=2)
    return intent


def _flow():
    intent_repo = InMemoryDailyIntentRepository()
    evening_repo = InMemoryEveningReflectionRepository()
    flow = EveningReflectionFlow(intent_repo, evening_repo, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()))
    return flow, intent_repo, evening_repo


# --- reflection can begin / complete ---------------------------------------------------------


def test_reflection_can_begin_with_an_open_question():
    flow, intent_repo, _ = _flow()
    _seed_intent(intent_repo, (PlannedActivity(description="Ship the report"),))
    prompt = flow.open(organization_id=1, user_id=2, today=date(2026, 8, 13))
    assert prompt.open_question == "How did today go?"
    assert "Ship the report" in prompt.context_summary


def test_reflection_can_complete_when_everything_is_resolved():
    flow, intent_repo, _ = _flow()
    _seed_intent(intent_repo, (PlannedActivity(description="Ship the report"),))
    result = flow.submit(organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="Finished the report.")
    assert result.needs_follow_up is False
    assert result.reflection is not None


def test_natural_user_input_updates_reflection_state_without_a_questionnaire():
    """One free-form sentence, not a form with a field per activity."""
    flow, intent_repo, _ = _flow()
    _seed_intent(intent_repo, (PlannedActivity(description="Ship the report"), PlannedActivity(description="Review the budget")))
    result = flow.submit(
        organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13),
        user_text="Finished the report and reviewed the budget.",
    )
    assert result.needs_follow_up is False
    statuses = {r.activity.description: r.status for r in result.reconciliations}
    assert statuses["Ship the report"] == ReconciliationStatus.COMPLETED
    assert statuses["Review the budget"] == ReconciliationStatus.COMPLETED


# --- every reconciliation status is distinguishable -------------------------------------------


def test_completed_work_is_recorded_correctly():
    flow, intent_repo, _ = _flow()
    _seed_intent(intent_repo, (PlannedActivity(description="Ship the milestone"),))
    result = flow.submit(organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="Shipped the milestone.")
    assert result.reconciliations[0].status == ReconciliationStatus.COMPLETED


def test_postponed_work_is_distinguishable_via_follow_up():
    flow, intent_repo, _ = _flow()
    _seed_intent(intent_repo, (PlannedActivity(description="Study transformers"),))
    r1 = flow.submit(organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="Didn't get to study transformers.")
    assert r1.needs_follow_up is True
    final = flow.resolve_follow_up(
        organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13),
        ambiguous_activities=r1.ambiguous_activities, follow_up_text="I ran out of time.",
        resolved_evidence_by_description=r1.resolved_evidence_by_description, resolved_accomplishments=r1.resolved_accomplishments,
    )
    assert final.reconciliations[0].status == ReconciliationStatus.POSTPONED


def test_cancelled_work_is_distinguishable():
    flow, intent_repo, _ = _flow()
    _seed_intent(intent_repo, (PlannedActivity(description="Refactor the legacy module"),))
    result = flow.submit(
        organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13),
        user_text="Cancelled refactoring the legacy module - no longer needed.",
    )
    assert result.needs_follow_up is False
    assert result.reconciliations[0].status == ReconciliationStatus.CANCELLED


def test_blocked_work_is_distinguishable():
    flow, intent_repo, _ = _flow()
    _seed_intent(intent_repo, (PlannedActivity(description="Deploy the service"),))
    result = flow.submit(
        organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13),
        user_text="Deploying the service is blocked, waiting on infra access.",
    )
    assert result.reconciliations[0].status == ReconciliationStatus.BLOCKED


def test_superseded_work_is_distinguishable():
    flow, intent_repo, _ = _flow()
    _seed_intent(intent_repo, (PlannedActivity(description="Write documentation"),))
    result = flow.submit(
        organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13),
        user_text="Didn't write documentation - priorities changed and I handled a client issue instead.",
    )
    assert result.needs_follow_up is False
    assert result.reconciliations[0].status == ReconciliationStatus.SUPERSEDED


def test_intentional_rest_is_distinguishable_from_every_other_status():
    flow, intent_repo, _ = _flow()
    _seed_intent(intent_repo, (PlannedActivity(description="Ship the report"),), day_type=DayType.REST, is_rest_day=True)
    result = flow.submit(organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="Today I just want to rest.")
    assert result.reconciliations[0].status == ReconciliationStatus.RESTED
    assert result.reconciliations[0].status not in (
        ReconciliationStatus.CANCELLED,
        ReconciliationStatus.INCOMPLETE,
        ReconciliationStatus.UNKNOWN,
    )


def test_rest_day_is_never_treated_as_failure_low_productivity_or_missed_commitments():
    flow, intent_repo, _ = _flow()
    _seed_intent(intent_repo, (PlannedActivity(description="Ship the report"),), day_type=DayType.REST, is_rest_day=True)
    result = flow.submit(organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="Today I just want to rest.")
    # No recommendation implies anything was missed - only PROTECT_REST.
    assert len(result.tomorrow_recommendations) == 1
    assert result.tomorrow_recommendations[0].kind.value == "protect_rest"


def test_tomorrow_resumes_normal_operation_after_a_rest_day():
    from app.services.personal_os.morning_flow import MorningInteractionFlow

    intent_repo = InMemoryDailyIntentRepository()
    evening_repo = InMemoryEveningReflectionRepository()
    runtime = RuntimeAdapter(runtime=_FakeRuntime())
    _seed_intent(intent_repo, (PlannedActivity(description="Ship the report"),), day_type=DayType.REST, is_rest_day=True)
    evening = EveningReflectionFlow(intent_repo, evening_repo, runtime_adapter=runtime)
    evening.submit(organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="Rested today.")

    morning = MorningInteractionFlow(intent_repo, evening_repository=evening_repo, runtime_adapter=runtime)
    tomorrow = morning.submit(organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 14), user_text="Back to work today.")
    assert tomorrow.intent.day_type == DayType.WORK  # normal operation resumed, not stuck in rest


# --- user explanations are preserved, distinct from inference ---------------------------------


def test_user_explanations_are_preserved_verbatim():
    flow, intent_repo, _ = _flow()
    _seed_intent(intent_repo, (PlannedActivity(description="Study AI systems"),))
    r1 = flow.submit(organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="Didn't study AI systems.")
    final = flow.resolve_follow_up(
        organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13),
        ambiguous_activities=r1.ambiguous_activities,
        follow_up_text="An unexpected meeting came up and took two hours.",
        resolved_evidence_by_description=r1.resolved_evidence_by_description, resolved_accomplishments=r1.resolved_accomplishments,
    )
    assert final.reconciliations[0].evidence.note == "An unexpected meeting came up and took two hours."


def test_observations_remain_distinct_from_inference():
    from app.services.personal_os.evening_flow import build_hypothesis, build_reasoning_trace, build_user_explanations
    from app.services.personal_os.reasoning import ObservedFact, UserExplanation, Hypothesis
    from app.services.personal_os.reconciliation import ReconciliationEvidence, reconcile

    r1 = reconcile(PlannedActivity(description="Task A"), ReconciliationEvidence(explicitly_postponed=True, note="meeting"))
    r2 = reconcile(PlannedActivity(description="Task B"), ReconciliationEvidence(explicitly_postponed=True, note="meeting"))
    facts = build_reasoning_trace((r1, r2))
    explanations = build_user_explanations((r1, r2))
    hypothesis = build_hypothesis(facts, explanations)

    assert all(isinstance(f, ObservedFact) for f in facts)
    assert all(isinstance(e, UserExplanation) for e in explanations)
    assert isinstance(hypothesis, Hypothesis)
    bases = {f.basis if hasattr(f, "basis") else "fact" for f in facts} | {e.basis for e in explanations} | {hypothesis.basis}
    assert len(bases) == 3  # fact-shaped (no basis attr = implicitly OBSERVED_FACT), user_explanation, hypothesis - never merged


def test_never_assumes_a_reason_without_evidence():
    """§4: never store "Victor is procrastinating" unless the user
    explicitly says that. An ambiguous activity with no follow-up
    resolves to UNKNOWN, never to an assumed reason."""
    flow, intent_repo, _ = _flow()
    _seed_intent(intent_repo, (PlannedActivity(description="Study AI systems"),))
    result = flow.submit(organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="Didn't study AI systems.")
    assert result.needs_follow_up is True
    # No follow-up given - the flow does not guess; it stops and asks.
    assert "was that because" in result.follow_up_question.lower()


# --- runtime integration ------------------------------------------------------------------


def test_evening_flow_invokes_the_real_runtime_adapter():
    flow, intent_repo, _ = _flow()
    _seed_intent(intent_repo, (PlannedActivity(description="Ship the report"),))
    flow.submit(organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="Shipped it.")
    assert len(flow.runtime_adapter.runtime.requests) == 1
