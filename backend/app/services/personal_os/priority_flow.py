"""PriorityIntelligenceFlow (P5 §13, §25-§27): the seam connecting Day
Mode, Personal State/Missions, and P1-P4's own already-persisted records
into a daily Core 5 + Optional 2 - the "state/priority seam that future
integrations can populate" §13 asks for, not the full external-data
morning briefing (deliberately out of scope this milestone, per §24).

Deliberately separate from MorningInteractionFlow (morning_flow.py):
that flow's own job is establishing today's DailyIntent (what kind of
day, what's planned) and is already tested end to end across P1-P4;
this flow's job is ranking candidates ACROSS every source P5 introduces
(DailyIntent, Mission, Pattern, Experiment) using Day Mode as one input
among several. Composing the two into one longer conversation is a
future integration's own job (§13's own explicit "do not build the full
external-data morning briefing"), not something this milestone forces by
rewriting morning_flow.py's already-tested contract.

Deterministic core (candidate gathering, scoring, ranking, override)
lives entirely in priority.py/candidate_sources.py; this module's only
generative step is phrasing an ALREADY-RANKED, ALREADY-EXPLAINED item
conversationally - mirroring pattern_flow.py's/experiment_flow.py's own
"compute first, narrate second" discipline exactly (§27)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.types import RuntimeRequest
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.context.types import ContextItem, ContextPackage, ContextSection
from app.services.prompt_builder.builder import PromptBuilder
from app.services.personal_os.candidate_sources import from_daily_intent, from_experiments, from_missions, from_pattern_recommendations
from app.services.personal_os.day_mode import DayMode, DayModeKind, infer_day_mode
from app.services.personal_os.experiment_repository import ExperimentRepository
from app.services.personal_os.mission_repository import MissionRepository
from app.services.personal_os.pattern_repository import PatternRepository
from app.services.personal_os.priority import CandidateItem, OverrideResult, PriorityConfig, PriorityExplanation, PriorityScore, apply_override, explain, rank_candidates
from app.services.personal_os.repository import DailyIntentRepository
from app.services.personal_os.shared.types import LifeDomain


@dataclass(frozen=True)
class PriorityEntry:
    """One ranked item, ready to present - the deterministic score/
    explanation plus the one generative rephrasing of it, kept as
    separate fields (never merged) so a caller can render or test each
    independently, matching PatternSurfacing's own precedent exactly."""

    score: PriorityScore
    explanation: PriorityExplanation
    narrative: str


@dataclass(frozen=True)
class PriorityPresentation:
    core: tuple[PriorityEntry, ...]
    optional: tuple[PriorityEntry, ...]
    day_mode: DayMode | None
    closing_question: str = "Anything else you want to add or remove?"


class PriorityIntelligenceFlow:
    def __init__(
        self,
        intent_repository: DailyIntentRepository,
        mission_repository: MissionRepository,
        pattern_repository: PatternRepository,
        experiment_repository: ExperimentRepository,
        runtime_adapter: RuntimeAdapter | None = None,
        default_provider: ProviderName = ProviderName.OPENAI,
        config: PriorityConfig | None = None,
    ) -> None:
        self.intent_repository = intent_repository
        self.mission_repository = mission_repository
        self.pattern_repository = pattern_repository
        self.experiment_repository = experiment_repository
        self.runtime_adapter = runtime_adapter or RuntimeAdapter()
        self.default_provider = default_provider
        self.config = config or PriorityConfig()

    def ask_day_mode(self) -> str:
        """§11's own literal question - asked before any ranking is
        produced, never inferred silently."""
        return "Good morning. What kind of day are we having?"

    @staticmethod
    def resolve_day_mode(user_text: str) -> DayMode:
        """A recognized keyword match (day_mode.infer_day_mode), or the
        user's own words preserved verbatim as a CUSTOM day mode (§11's
        own "allow a user-defined day mode") - never silently discarded
        just because it didn't match a known keyword."""
        inferred = infer_day_mode(user_text)
        if inferred is not None:
            return inferred
        return DayMode(kind=DayModeKind.CUSTOM, custom_label=user_text, stated_by_user=True)

    def gather_candidates(self, *, organization_id: int, user_id: int, today: date) -> tuple[CandidateItem, ...]:
        """§26: assembles candidates from every already-existing source
        this milestone connects to - never a new repository, never
        invented content. Each source function is itself a pure,
        independently-tested transformation (candidate_sources.py)."""
        candidates: list[CandidateItem] = []

        intent = self.intent_repository.get_for_date(organization_id=organization_id, user_id=user_id, intent_date=today)
        if intent is not None:
            candidates.extend(from_daily_intent(intent))

        candidates.extend(self.gather_non_intent_candidates(organization_id=organization_id, user_id=user_id))
        return tuple(candidates)

    def gather_non_intent_candidates(self, *, organization_id: int, user_id: int) -> tuple[CandidateItem, ...]:
        """Missions/Patterns/Experiments only - factored out of
        gather_candidates() (P6.2) so a caller with its own, richer
        notion of "today's activities" (living_day_flow.py's own
        LivingDayState, which supersedes plain DailyIntent once a day
        starts evolving) can still reuse this exact same candidate
        gathering for everything else, without re-querying three
        repositories itself or risking the two candidate sets silently
        drifting apart."""
        candidates: list[CandidateItem] = []

        missions = self.mission_repository.list_active(organization_id=organization_id, user_id=user_id)
        candidates.extend(from_missions(missions))

        patterns = self.pattern_repository.list_active(organization_id=organization_id, user_id=user_id)
        candidates.extend(from_pattern_recommendations(patterns))

        experiments = self.experiment_repository.list_active(organization_id=organization_id, user_id=user_id)
        candidates.extend(from_experiments(experiments))

        return tuple(candidates)

    def build_ranking(
        self,
        *,
        organization_id: int,
        user_id: int,
        today: date,
        available_hours: float,
        day_mode: DayMode | None = None,
    ):
        candidates = self.gather_candidates(organization_id=organization_id, user_id=user_id, today=today)
        return rank_candidates(candidates, today=today, available_hours=available_hours, day_mode=day_mode, config=self.config)

    def apply_hold(
        self,
        *,
        organization_id: int,
        user_id: int,
        today: date,
        available_hours: float,
        day_mode: DayMode | None,
        hold_domains: tuple[LifeDomain, ...],
    ) -> OverrideResult:
        """§13's own worked example ("Hold all work today...") and §21's
        "the OS should adapt" - re-gathers the same candidates and
        re-ranks with the requested domains held, never deleting or
        marking anything a failure."""
        candidates = self.gather_candidates(organization_id=organization_id, user_id=user_id, today=today)
        return apply_override(candidates, today=today, available_hours=available_hours, day_mode=day_mode, hold_domains=hold_domains, config=self.config)

    def present(self, ranking, *, organization_id: int, today: date, conversation_id: int | None = None) -> PriorityPresentation:
        """Evidence/score/explanation -> one generative rephrasing each
        (§12's "Priority, why it matters, deadline/time, suggested next
        action" shape) - the deterministic explanation is computed first
        and handed to the Runtime; the Runtime is never asked to decide
        what matters, only to phrase what already does."""
        core = tuple(self._entry(score, organization_id=organization_id, today=today, conversation_id=conversation_id) for score in ranking.core)
        optional = tuple(self._entry(score, organization_id=organization_id, today=today, conversation_id=conversation_id) for score in ranking.optional)
        return PriorityPresentation(core=core, optional=optional, day_mode=ranking.day_mode)

    def _entry(self, score: PriorityScore, *, organization_id: int, today: date, conversation_id: int | None) -> PriorityEntry:
        explanation = explain(score, today=today)
        narrative = self._narrate(score, explanation, organization_id, conversation_id)
        return PriorityEntry(score=score, explanation=explanation, narrative=narrative)

    def _narrate(self, score: PriorityScore, explanation: PriorityExplanation, organization_id: int, conversation_id: int | None) -> str:
        """The one real Runtime integration point in this flow - mirrors
        pattern_flow.py's/experiment_flow.py's own _narrate() exactly.
        The recommendation, its facts, and its inference are all already
        decided before this call; the Runtime only turns them into one
        readable paragraph, and an equally honest deterministic fallback
        exists for when no provider is configured (every other Personal
        OS flow's own discipline)."""
        package = ContextPackage(
            sections=[
                ContextSection(
                    resource_type="priority_item",
                    items=[
                        ContextItem(
                            resource_type="priority_item",
                            resource_id=0,
                            content=f"{score.item.description}: {' '.join(explanation.facts)} {explanation.inference}",
                            score=score.total,
                            created_at=datetime.now(UTC),
                        )
                    ],
                )
            ],
            estimated_tokens=0,
            item_count=1,
            truncated=False,
        )
        prompt_query = (
            f'Explain, in 1-2 short sentences, why "{score.item.description}" matters today. '
            f"Facts: {' '.join(explanation.facts)} {explanation.inference} {explanation.recommendation} "
            "State this as a suggestion, never a command - never say the user 'must' do this."
        )
        prompt_package = PromptBuilder().build(prompt_query, package)
        runtime_request = RuntimeRequest(
            organization_id=organization_id,
            prompt_package=prompt_package,
            provider=self.default_provider,
            conversation_id=conversation_id,
            parent_shared=SharedExecutionContext(organization_id=organization_id),
        )
        response = self.runtime_adapter.execute(runtime_request)
        if response.success and response.conversation_response:
            return response.conversation_response.text
        return f"{explanation.recommendation} {' '.join(explanation.facts)} {explanation.inference}"
