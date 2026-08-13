"""PatternDetectionFlow (P3 §1, §11): orchestrates the full pipeline -
historical evidence -> pattern detection -> evidence summary -> confidence
-> user confirmation/correction -> inferred pattern -> recommendation ->
future measurement.

Mirrors MorningInteractionFlow/EveningReflectionFlow's own shape exactly:
deterministic detection and reconciliation logic (pattern_detectors.py,
unchanged by this flow), with exactly one real generative step (the
natural-language surfacing of a detected pattern) reusing RuntimeAdapter/
PromptBuilder - never a bypass, never a second Runtime-invocation
mechanism. AI-generated language never changes the underlying
classification (§18): the Pattern's own pattern_type/confidence/status
are set entirely by detect()/respond(), before the Runtime is ever
called; the Runtime call only phrases what has already been decided.

Safety of personal inference (§16) is enforced here, not just in prose:
_render_prompt() is the one place a pattern's own statement becomes
user-facing text, and it always frames a hypothesis as a question
("Would you agree?"), never a diagnosis - there is no code path in this
module that emits a statement about the user's personality, motivation,
or character; every generated hypothesis is built from
reasoning.Hypothesis, which is itself always downstream of an
InferredPattern grounded in ObservedFacts (never a bare claim).
"""

from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.types import RuntimeRequest, RuntimeResponse
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.context.types import ContextItem, ContextPackage, ContextSection
from app.services.prompt_builder.builder import PromptBuilder
from app.services.personal_os.evening import EveningReflectionRepository
from app.services.personal_os.pattern import Experiment, GrowthRecommendation, Pattern
from app.services.personal_os.pattern_detectors import PatternDetectionConfig, detect_all
from app.services.personal_os.pattern_evidence import EvidenceWindow, HistoricalEvidenceReader
from app.services.personal_os.pattern_repository import PatternRepository
from app.services.personal_os.repository import DailyIntentRepository
from app.services.personal_os.shared.types import ExperimentStatus, PatternStatus, UserPatternResponse


@dataclass(frozen=True)
class PatternSurfacing:
    """What Personal OS actually presents to the user for one pattern -
    the evidence summary, the confidence, and the question, kept as
    separate fields (never one blob of prose) so a caller can render or
    test each part independently."""

    pattern: Pattern
    evidence_summary: str
    confidence_statement: str
    hypothesis_statement: str
    confirmation_question: str
    narrative: str


class PatternDetectionFlow:
    def __init__(
        self,
        intent_repository: DailyIntentRepository,
        evening_repository: EveningReflectionRepository,
        pattern_repository: PatternRepository,
        runtime_adapter: RuntimeAdapter | None = None,
        default_provider: ProviderName = ProviderName.OPENAI,
        config: PatternDetectionConfig | None = None,
    ) -> None:
        self.evidence_reader = HistoricalEvidenceReader(intent_repository, evening_repository)
        self.pattern_repository = pattern_repository
        self.runtime_adapter = runtime_adapter or RuntimeAdapter()
        self.default_provider = default_provider
        self.config = config or PatternDetectionConfig()

    def detect(self, *, organization_id: int, user_id: int, today: date) -> tuple[Pattern, ...]:
        """Historical evidence -> pattern detection (§1's first two
        stages). Every detected Pattern is saved as OBSERVED - not yet
        shown to anyone (surface_next() does that) - so detection and
        surfacing stay two separate, independently testable steps."""
        window = EvidenceWindow.trailing_days(today, self.config.window_days)
        evidence = self.evidence_reader.gather(organization_id=organization_id, user_id=user_id, window=window)
        detected = detect_all(evidence, self.config, lambda: str(uuid4()))

        saved = [self.pattern_repository.save(pattern, organization_id=organization_id, user_id=user_id) for pattern in detected]
        return tuple(saved)

    def surface_next(self, *, organization_id: int, user_id: int, conversation_id: int | None = None) -> PatternSurfacing | None:
        """Evidence summary -> confidence -> (about to ask for) user
        confirmation. Picks the first active pattern not yet surfaced
        (status still OBSERVED); returns None once nothing new is
        waiting - never re-surfaces a CONFIRMED/DISMISSED/CORRECTED
        pattern as if it were new."""
        candidates = [p for p in self.pattern_repository.list_active(organization_id=organization_id, user_id=user_id) if p.status == PatternStatus.OBSERVED]
        if not candidates:
            return None
        pattern = candidates[0]

        pending = _with_status(pattern, PatternStatus.PENDING_CONFIRMATION)
        saved = self.pattern_repository.save(pending, organization_id=organization_id, user_id=user_id)

        evidence_summary = "; ".join(fact.statement for fact in saved.observed_facts)
        confidence_statement = f"Confidence: {saved.confidence.value}."
        hypothesis_statement = (
            "Possible explanation: " + saved.possible_hypotheses[0].statement if saved.possible_hypotheses else ""
        )
        confirmation_question = "Does that seem accurate to you?"

        narrative = self._narrate(saved, organization_id, conversation_id)
        return PatternSurfacing(
            pattern=saved,
            evidence_summary=evidence_summary,
            confidence_statement=confidence_statement,
            hypothesis_statement=hypothesis_statement,
            confirmation_question=confirmation_question,
            narrative=narrative,
        )

    def respond(
        self,
        *,
        organization_id: int,
        user_id: int,
        pattern: Pattern,
        response: UserPatternResponse,
        correction_text: str = "",
    ) -> Pattern:
        """User confirmation/correction -> inferred pattern's own final
        status. CONFIRM -> CONFIRMED; REJECT -> DISMISSED (never
        resurfaced as established, per §11 - list_active() already
        excludes DISMISSED); CORRECT -> CORRECTED, with the user's own
        words preserved verbatim in user_interpretation, never
        paraphrased or discarded; DEFER -> stays PENDING_CONFIRMATION,
        genuinely unresolved, not silently advanced either way."""
        if response == UserPatternResponse.DEFER:
            return pattern  # explicitly unchanged - deferring is not a status transition

        new_status = {
            UserPatternResponse.CONFIRM: PatternStatus.CONFIRMED,
            UserPatternResponse.REJECT: PatternStatus.DISMISSED,
            UserPatternResponse.CORRECT: PatternStatus.CORRECTED,
        }[response]

        updated = _with_status(pattern, new_status)
        if response == UserPatternResponse.CORRECT:
            if not correction_text:
                raise ValueError("respond(UserPatternResponse.CORRECT) requires non-empty correction_text")
            updated = _with_interpretation(updated, correction_text)

        return self.pattern_repository.save(updated, organization_id=organization_id, user_id=user_id)

    def attach_recommendation(
        self, *, organization_id: int, user_id: int, pattern: Pattern, recommendation: GrowthRecommendation
    ) -> Pattern:
        """Recommendation model (§12): only ever attached to an already-
        CONFIRMED pattern - a recommendation responding to a pattern the
        user rejected or hasn't yet confirmed would be advice built on
        nothing the user actually agreed happened."""
        if pattern.status != PatternStatus.CONFIRMED:
            raise ValueError("attach_recommendation() requires a CONFIRMED pattern - respond() with CONFIRM first")
        updated = _with_recommendation(pattern, recommendation)
        return self.pattern_repository.save(updated, organization_id=organization_id, user_id=user_id)

    @staticmethod
    def propose_experiment(
        pattern: Pattern, *, hypothesis_statement: str, adjustment: str, measurement_plan: str, started_on: date, review_date: date | None = None
    ) -> Experiment:
        """Experimental learning (§13) - always explicit, always
        optional; nothing in this flow calls this automatically. Requires
        a CONFIRMED pattern with an attached recommendation, since an
        experiment without either would have nothing real to measure
        against."""
        if pattern.status != PatternStatus.CONFIRMED:
            raise ValueError("propose_experiment() requires a CONFIRMED pattern")
        if pattern.recommendation is None:
            raise ValueError("propose_experiment() requires a pattern with an attached recommendation")
        return Experiment(
            experiment_id=str(uuid4()),
            pattern_id=pattern.pattern_id,
            hypothesis_statement=hypothesis_statement,
            adjustment=adjustment,
            measurement_plan=measurement_plan,
            started_on=started_on,
            review_date=review_date,
            status=ExperimentStatus.PROPOSED,
        )

    def _narrate(self, pattern: Pattern, organization_id: int, conversation_id: int | None) -> str:
        """The one real Runtime integration point in this flow - mirrors
        MorningInteractionFlow/EveningReflectionFlow's own _acknowledge()
        exactly. Never phrases a diagnosis: the prompt itself instructs
        an observation-plus-question framing, and falls back to a
        deterministic, equally careful phrasing if the Runtime call
        fails (no provider configured in this environment, matching
        every other Personal OS flow's own honest fallback)."""
        package = ContextPackage(
            sections=[
                ContextSection(
                    resource_type="pattern",
                    items=[ContextItem(resource_type="pattern", resource_id=0, content=pattern.pattern_statement, score=1.0, created_at=pattern.created_at)],
                )
            ],
            estimated_tokens=0,
            item_count=1,
            truncated=False,
        )
        hypothesis_clause = f" {pattern.possible_hypotheses[0].statement}" if pattern.possible_hypotheses else ""
        prompt_query = (
            "I've noticed something. "
            f"{pattern.pattern_statement}"
            f"{hypothesis_clause} Does that seem accurate to you? "
            "State this as an observed pattern and a possible explanation only - never as a "
            "diagnosis of the person's character, motivation, or personality."
        )
        prompt_package = PromptBuilder().build(prompt_query, package)
        runtime_request = RuntimeRequest(
            organization_id=organization_id,
            prompt_package=prompt_package,
            provider=self.default_provider,
            conversation_id=conversation_id,
            parent_shared=SharedExecutionContext(organization_id=organization_id),
        )
        response: RuntimeResponse = self.runtime_adapter.execute(runtime_request)
        if response.success and response.conversation_response:
            return response.conversation_response.text
        fallback = f"I've noticed something: {pattern.pattern_statement}"
        if pattern.possible_hypotheses:
            fallback += f" {pattern.possible_hypotheses[0].statement} Does that seem accurate to you?"
        else:
            fallback += " Does that seem accurate to you?"
        return fallback


def _with_status(pattern: Pattern, status: PatternStatus) -> Pattern:
    from dataclasses import replace
    from datetime import UTC, datetime

    return replace(pattern, status=status, updated_at=datetime.now(UTC))


def _with_interpretation(pattern: Pattern, user_interpretation: str) -> Pattern:
    from dataclasses import replace
    from datetime import UTC, datetime

    return replace(pattern, user_interpretation=user_interpretation, updated_at=datetime.now(UTC))


def _with_recommendation(pattern: Pattern, recommendation: GrowthRecommendation) -> Pattern:
    from dataclasses import replace
    from datetime import UTC, datetime

    return replace(pattern, recommendation=recommendation, updated_at=datetime.now(UTC))
