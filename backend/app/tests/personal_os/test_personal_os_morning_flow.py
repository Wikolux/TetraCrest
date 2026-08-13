"""MorningInteractionFlow (§3): context-first, free-form intent,
continuation vs. change, and the real RuntimeAdapter integration point."""

from datetime import date

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.runtime.types import RuntimeResponse
from app.services.ai.shared.response import AIResponseMetadata, ProviderResponse
from app.services.ai.conversation.types import ConversationResponse
from app.services.ai.providers.enums import ProviderName
from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.morning_flow import MorningInteractionFlow
from app.services.personal_os.repository import InMemoryDailyIntentRepository
from app.services.personal_os.shared.types import DayType


class _FakeRuntime:
    def __init__(self, text="Understood."):
        self.text = text
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        response = ConversationResponse(
            text=self.text,
            response=ProviderResponse(metadata=AIResponseMetadata(provider=ProviderName.OPENAI, model="test")),
        )
        return RuntimeResponse(success=True, conversation_response=response)


def _flow(repo=None, runtime=None):
    return MorningInteractionFlow(repo or InMemoryDailyIntentRepository(), runtime_adapter=RuntimeAdapter(runtime=runtime or _FakeRuntime()))


def test_open_reports_no_carryover_when_nothing_precedes_it():
    prompt = _flow().open(organization_id=1, user_id=2, today=date(2026, 8, 13))
    assert "nothing carried over" in prompt.context_summary.lower()


def test_open_summarizes_carried_over_items_before_asking_anything():
    repo = InMemoryDailyIntentRepository()
    yesterday = DailyIntent(
        intent_date=date(2026, 8, 12),
        stated_intention="Ship it",
        day_type=DayType.WORK,
        planned_activities=(PlannedActivity(description="Finish the deck"),),
    )
    repo.save(yesterday, organization_id=1, user_id=2)

    prompt = _flow(repo).open(organization_id=1, user_id=2, today=date(2026, 8, 13))
    assert "Finish the deck" in prompt.context_summary
    assert prompt.open_question  # a question is always asked, never skipped


def test_continuation_from_previous_day_carries_planned_activities_forward():
    repo = InMemoryDailyIntentRepository()
    yesterday = DailyIntent(
        intent_date=date(2026, 8, 12),
        stated_intention="Ship it",
        day_type=DayType.WORK,
        planned_activities=(PlannedActivity(description="Finish the deck"),),
    )
    repo.save(yesterday, organization_id=1, user_id=2)

    response = _flow(repo).submit(
        organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="Continuing as planned, same as yesterday."
    )
    assert response.intent.continuation_of_date == date(2026, 8, 12)
    assert response.intent.planned_activities == yesterday.planned_activities


def test_new_priorities_can_be_introduced_when_the_day_is_different():
    """Mirrors the build spec's own worked example verbatim."""
    response = _flow().submit(
        organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="Today is different. I want to study and apply for jobs."
    )
    assert response.intent.continuation_of_date is None
    assert len(response.intent.new_priorities) == 1
    assert response.intent.day_type == DayType.MIXED  # study + apply/jobs both match


def test_rest_intention_is_recognized_and_marked_a_rest_day():
    response = _flow().submit(organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="I need a rest day today.")
    assert response.intent.day_type == DayType.REST
    assert response.intent.is_rest_day is True


def test_submit_rejects_empty_user_text():
    import pytest

    with pytest.raises(ValueError):
        _flow().submit(organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="")


def test_morning_flow_saves_the_reconciled_intent():
    repo = InMemoryDailyIntentRepository()
    _flow(repo).submit(organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="Work day, usual priorities.")
    saved = repo.get_for_date(organization_id=1, user_id=2, intent_date=date(2026, 8, 13))
    assert saved is not None


def test_morning_flow_invokes_the_real_runtime_adapter_not_a_bypass():
    runtime = _FakeRuntime()
    _flow(runtime=runtime).submit(organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="Work day.")
    assert len(runtime.requests) == 1
    assert runtime.requests[0].organization_id == 1


def test_acknowledgment_falls_back_honestly_when_the_runtime_call_fails():
    class _FailingRuntime:
        def execute(self, request):
            return RuntimeResponse(success=False)

    response = _flow(runtime=_FailingRuntime()).submit(
        organization_id=1, user_id=2, conversation_id=None, today=date(2026, 8, 13), user_text="Work day."
    )
    assert "work" in response.acknowledgment.lower()


# --- tomorrow context (P2 §8): recommendations surfaced, never merged into commitments -------


def test_todays_reflection_can_generate_tomorrow_context():
    from app.services.personal_os.daily_intent import PlannedActivity
    from app.services.personal_os.evening import EveningReflection, InMemoryEveningReflectionRepository
    from app.services.personal_os.reconciliation import ReconciliationEvidence, reconcile

    intent_repo = InMemoryDailyIntentRepository()
    evening_repo = InMemoryEveningReflectionRepository()
    yesterday = DailyIntent(
        intent_date=date(2026, 8, 12),
        stated_intention="Study AI",
        day_type=DayType.STUDY,
        planned_activities=(PlannedActivity(description="Study AI systems"),),
    )
    intent_repo.save(yesterday, organization_id=1, user_id=2)
    record = reconcile(PlannedActivity(description="Study AI systems"), ReconciliationEvidence(explicitly_postponed=True, note="meeting"))
    evening_repo.save(
        EveningReflection(reflection_date=date(2026, 8, 12)), (record,), organization_id=1, user_id=2, daily_intent_id=None
    )

    morning = MorningInteractionFlow(intent_repo, evening_repository=evening_repo, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()))
    prompt = morning.open(organization_id=1, user_id=2, today=date(2026, 8, 13))
    assert len(prompt.recommendations) == 1
    assert prompt.recommendations[0].subject == "Study AI systems"


def test_recommendations_are_not_automatically_commitments():
    """A recommendation appears in MorningPrompt.recommendations, never
    silently merged into context_summary's own carried-over commitments
    - the two stay separate fields, never combined into one list."""
    from app.services.personal_os.daily_intent import PlannedActivity
    from app.services.personal_os.evening import EveningReflection, InMemoryEveningReflectionRepository
    from app.services.personal_os.reconciliation import ReconciliationEvidence, reconcile

    intent_repo = InMemoryDailyIntentRepository()
    evening_repo = InMemoryEveningReflectionRepository()
    yesterday = DailyIntent(
        intent_date=date(2026, 8, 12),
        stated_intention="Study AI",
        day_type=DayType.STUDY,
        planned_activities=(PlannedActivity(description="Study AI systems"),),
    )
    intent_repo.save(yesterday, organization_id=1, user_id=2)
    record = reconcile(PlannedActivity(description="Study AI systems"), ReconciliationEvidence(explicitly_postponed=True))
    evening_repo.save(EveningReflection(reflection_date=date(2026, 8, 12)), (record,), organization_id=1, user_id=2, daily_intent_id=None)

    morning = MorningInteractionFlow(intent_repo, evening_repository=evening_repo, runtime_adapter=RuntimeAdapter(runtime=_FakeRuntime()))
    prompt = morning.open(organization_id=1, user_id=2, today=date(2026, 8, 13))
    assert "recommend" not in prompt.context_summary.lower()
    assert prompt.recommendations != ()


def test_original_plan_remains_recoverable_after_recommendations_are_surfaced():
    intent_repo = InMemoryDailyIntentRepository()
    yesterday = DailyIntent(intent_date=date(2026, 8, 12), stated_intention="Original plan text", day_type=DayType.WORK)
    intent_repo.save(yesterday, organization_id=1, user_id=2)

    fetched = intent_repo.get_latest_before(organization_id=1, user_id=2, before=date(2026, 8, 13))
    assert fetched.stated_intention == "Original plan text"


def test_no_recommendations_surfaced_when_no_evening_repository_is_wired():
    """Backward compatible with P1 - a morning flow built without an
    evening_repository still works, simply with zero recommendations."""
    flow = _flow()
    prompt = flow.open(organization_id=1, user_id=2, today=date(2026, 8, 13))
    assert prompt.recommendations == ()
