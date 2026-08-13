"""ExperimentFlow (P4 §2-§4, §7-§14): the second half of Personal OS's
own Observe -> Adjust -> Measure loop - everything from an already-
proposed Experiment (PatternDetectionFlow.propose_experiment(), P3 §13/
P4 §5) through approval, activation, review, and the user's final
keep/modify/stop/continue decision.

Split from PatternDetectionFlow deliberately: proposing a well-formed
experiment needs a Pattern (it validates CONFIRMED status and a
recommendation, and it inherits pattern_id) - that's Pattern's own
concern. Everything from approval onward needs only the Experiment
itself and fresh evidence; it never touches Pattern again. Keeping the
two flows separate means this module's own evidence-to-outcome pipeline
can be tested, and reasoned about, without any Pattern-confirmation
machinery in the way.

Every lifecycle transition here persists a NEW version under the SAME
experiment_id (ExperimentRepository's own append-only convention) -
never a mutation, so the full history (original proposal, approval,
activation, review, decision) is always retrievable via
ExperimentRepository.get_history() (§16).

Deterministic core (§18): review()'s measurement, comparison, and
outcome classification are entirely computed by experiment_measurement
.py before the Runtime is ever invoked - the one generative step
(_narrate_review()) only explains a result that has already been
decided, exactly mirroring pattern_flow.py's own _narrate() discipline.
"""

from dataclasses import replace
from datetime import UTC, date, datetime

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.types import RuntimeRequest
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.context.types import ContextItem, ContextPackage, ContextSection
from app.services.prompt_builder.builder import PromptBuilder
from app.services.personal_os.evening import EveningReflectionRepository
from app.services.personal_os.experiment import Experiment, ExperimentBaseline, ExperimentComparison
from app.services.personal_os.experiment_measurement import build_measurement, compare
from app.services.personal_os.experiment_repository import ExperimentRepository
from app.services.personal_os.pattern_detectors import PatternDetectionConfig
from app.services.personal_os.pattern_evidence import EvidenceWindow, HistoricalEvidenceReader
from app.services.personal_os.repository import DailyIntentRepository
from app.services.personal_os.shared.types import ExperimentOutcome, ExperimentStatus, ExperimentUserDecision


class ExperimentFlow:
    def __init__(
        self,
        intent_repository: DailyIntentRepository,
        evening_repository: EveningReflectionRepository,
        experiment_repository: ExperimentRepository,
        runtime_adapter: RuntimeAdapter | None = None,
        default_provider: ProviderName = ProviderName.OPENAI,
        config: PatternDetectionConfig | None = None,
    ) -> None:
        self.evidence_reader = HistoricalEvidenceReader(intent_repository, evening_repository)
        self.experiment_repository = experiment_repository
        self.runtime_adapter = runtime_adapter or RuntimeAdapter()
        self.default_provider = default_provider
        self.config = config or PatternDetectionConfig()

    # --- approval (§4) --------------------------------------------------------------------------

    def approve(self, *, organization_id: int, user_id: int, experiment: Experiment) -> Experiment:
        """§4: the explicit approval boundary - an experiment never
        becomes ACTIVE merely because it was proposed."""
        _require_status(experiment, ExperimentStatus.PROPOSED, "approve")
        return self._save(organization_id, user_id, replace(experiment, status=ExperimentStatus.APPROVED))

    def reject(self, *, organization_id: int, user_id: int, experiment: Experiment, reason: str = "") -> Experiment:
        """§4: "If rejected: Do not activate it." Modeled as an immediate,
        terminal STOPPED - never left ACTIVE by accident, and never
        resurfaced as a live proposal."""
        _require_status(experiment, ExperimentStatus.PROPOSED, "reject")
        return self._save(
            organization_id,
            user_id,
            replace(experiment, status=ExperimentStatus.STOPPED, decision=ExperimentUserDecision.STOP, decision_reason=reason),
        )

    def defer(self, experiment: Experiment) -> Experiment:
        """§4: "If deferred: Keep it available without treating it as
        active." Explicitly unchanged - mirrors PatternDetectionFlow
        .respond(DEFER)'s own no-op precedent exactly."""
        return experiment

    # --- activation (§2) ------------------------------------------------------------------------

    def activate(self, *, organization_id: int, user_id: int, experiment: Experiment, today: date) -> Experiment:
        _require_status(experiment, ExperimentStatus.APPROVED, "activate")
        return self._save(organization_id, user_id, replace(experiment, status=ExperimentStatus.ACTIVE, started_on=today))

    # --- review eligibility (§7) -----------------------------------------------------------------

    def list_ready_for_review(self, *, organization_id: int, user_id: int, today: date) -> tuple[Experiment, ...]:
        """§7: "The Personal OS should be able to identify EXPERIMENTS
        READY FOR REVIEW... Do not require the user to remember
        manually." ACTIVE experiments whose review_date has arrived are
        promoted to READY_FOR_REVIEW as a real, persisted transition -
        not merely a query result that forgets itself."""
        candidates = self.experiment_repository.list_ready_for_review(organization_id=organization_id, user_id=user_id, today=today)
        promoted = []
        for experiment in candidates:
            if experiment.status == ExperimentStatus.ACTIVE:
                experiment = self._save(organization_id, user_id, replace(experiment, status=ExperimentStatus.READY_FOR_REVIEW))
            promoted.append(experiment)
        return tuple(promoted)

    # --- review: evidence -> measurement -> comparison -> interpretation (§8-§12) ----------------

    def review(self, *, organization_id: int, user_id: int, experiment: Experiment, today: date, conversation_id: int | None = None) -> Experiment:
        """Collects real, persisted evidence over exactly
        [experiment.started_on, today] - never a period the caller
        silently changes (§8) - computes the deterministic comparison
        (experiment_measurement.compare(), §9-§11), and only then asks
        the Runtime to explain an already-decided result (§12)."""
        if experiment.status not in (ExperimentStatus.ACTIVE, ExperimentStatus.READY_FOR_REVIEW):
            raise ValueError(f"review() requires ACTIVE or READY_FOR_REVIEW, got {experiment.status.value}")

        window = EvidenceWindow(start=experiment.started_on, end=today)
        evidence = self.evidence_reader.gather(organization_id=organization_id, user_id=user_id, window=window)
        measurement = build_measurement(evidence, experiment.baseline.metric, experiment.baseline.category, window.start, window.end)
        comparison = compare(experiment.baseline, measurement, self.config)

        narrative = self._narrate_review(comparison, organization_id, conversation_id)
        updated = replace(
            experiment,
            status=ExperimentStatus.REVIEWED,
            comparison=comparison,
            review_narrative=narrative,
            review_outcome=comparison.observation_statement,
        )
        return self._save(organization_id, user_id, updated)

    # --- user review / decision (§13-§14) ---------------------------------------------------------

    def decide(
        self,
        *,
        organization_id: int,
        user_id: int,
        experiment: Experiment,
        decision: ExperimentUserDecision,
        today: date,
        reason: str = "",
        modification_notes: str = "",
        extended_review_date: date | None = None,
    ) -> Experiment:
        """§13-§14: KEEP/STOP are terminal; CONTINUE explicitly extends
        the measurement period (never silently - raises without a new
        review_date); MODIFY captures the change and starts the next
        measurement cycle, with the just-completed measurement becoming
        the new baseline (the honest "next cycle's before-picture" is
        what was actually just observed, not the original one); DEFER
        leaves the experiment exactly as reviewed, undecided."""
        _require_status(experiment, ExperimentStatus.REVIEWED, "decide")

        if decision == ExperimentUserDecision.DEFER:
            return experiment

        if decision == ExperimentUserDecision.KEEP:
            updated = replace(experiment, status=ExperimentStatus.KEPT, decision=decision, decision_reason=reason)

        elif decision == ExperimentUserDecision.STOP:
            updated = replace(experiment, status=ExperimentStatus.STOPPED, decision=decision, decision_reason=reason)

        elif decision == ExperimentUserDecision.CONTINUE:
            if extended_review_date is None:
                raise ValueError("decide(CONTINUE) requires extended_review_date - never silently alter the experiment (§14)")
            updated = replace(
                experiment, status=ExperimentStatus.ACTIVE, review_date=extended_review_date, decision=decision, decision_reason=reason
            )

        elif decision == ExperimentUserDecision.MODIFY:
            if not modification_notes:
                raise ValueError("decide(MODIFY) requires modification_notes (§14)")
            if experiment.comparison is None:
                raise ValueError("decide(MODIFY) requires a reviewed experiment with a comparison")
            new_baseline = _measurement_as_baseline(experiment.comparison.measurement)
            updated = replace(
                experiment,
                status=ExperimentStatus.APPROVED,
                adjustment=modification_notes,
                baseline=new_baseline,
                started_on=today,
                review_date=None,
                comparison=None,
                review_narrative="",
                review_outcome="",
                decision=decision,
                decision_reason=reason,
            )
        else:
            raise ValueError(f"Unhandled ExperimentUserDecision: {decision!r}")

        return self._save(organization_id, user_id, updated)

    def expire(self, *, organization_id: int, user_id: int, experiment: Experiment) -> Experiment:
        """An explicit, caller-invoked terminal state for an experiment
        no one ever returned to - no automatic time-based expiry exists
        (this backend has no scheduler for Personal OS), so EXPIRED is
        available but never applied silently."""
        if experiment.status in (ExperimentStatus.KEPT, ExperimentStatus.MODIFIED, ExperimentStatus.STOPPED, ExperimentStatus.EXPIRED):
            raise ValueError(f"expire() cannot be called on a terminal experiment (status={experiment.status.value})")
        return self._save(organization_id, user_id, replace(experiment, status=ExperimentStatus.EXPIRED))

    # --- internals ------------------------------------------------------------------------------

    def _save(self, organization_id: int, user_id: int, experiment: Experiment) -> Experiment:
        updated = replace(experiment, updated_at=datetime.now(UTC))
        return self.experiment_repository.save(updated, organization_id=organization_id, user_id=user_id)

    def _narrate_review(self, comparison: ExperimentComparison, organization_id: int, conversation_id: int | None) -> str:
        """The one real Runtime integration point in this flow - mirrors
        PatternDetectionFlow._narrate() exactly. The deterministic
        comparison result is computed BEFORE this is ever called and is
        never altered by it (§12, §18): this only explains what
        classify_outcome() already decided."""
        package = ContextPackage(
            sections=[
                ContextSection(
                    resource_type="experiment_comparison",
                    items=[
                        ContextItem(
                            resource_type="experiment_comparison",
                            resource_id=0,
                            content=comparison.observation_statement,
                            score=1.0,
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
            f"During the experiment period, the following was observed: {comparison.observation_statement} "
            f"Classification: {comparison.outcome.value} (confidence: {comparison.confidence.value}). "
            "Explain this result in one or two plain sentences. State only what was observed, and be explicit "
            "that causality has not been established - never claim the change caused the result, and never "
            "overclaim confidence beyond what was given."
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
        return f"{comparison.observation_statement} {_fallback_interpretation(comparison.outcome)}"


def _fallback_interpretation(outcome: ExperimentOutcome) -> str:
    """§9's OBSERVATION/INTERPRETATION/CAUSALITY split, as a deterministic
    fallback sentence when the Runtime call fails (no provider registered
    in this environment, matching every other Personal OS flow's own
    honest fallback) - never a stronger claim than the outcome itself
    supports."""
    if outcome == ExperimentOutcome.INSUFFICIENT_DATA:
        return "There isn't enough evidence yet to say anything about this."
    if outcome == ExperimentOutcome.INCONCLUSIVE:
        return "This is an early signal with limited evidence - promising but inconclusive; causality has not been established."
    if outcome == ExperimentOutcome.UNCHANGED:
        return "This does not show a meaningful change; causality has not been established either way."
    if outcome == ExperimentOutcome.IMPROVED:
        return "This is consistent with the change helping, though causality has not been established."
    return "This is consistent with the change not helping, though causality has not been established."


def _measurement_as_baseline(measurement) -> ExperimentBaseline:
    """MODIFY's own next-cycle baseline: the measurement just taken
    becomes the starting point for the modified adjustment - the same
    shape (metric, category, period, value, observation_count), just
    reinterpreted as a new "before" picture rather than an "after" one."""
    return ExperimentBaseline(
        metric=measurement.metric,
        category=measurement.category,
        period_start=measurement.period_start,
        period_end=measurement.period_end,
        value=measurement.value,
        observation_count=measurement.observation_count,
    )


def _require_status(experiment: Experiment, expected: ExperimentStatus, action: str) -> None:
    if experiment.status != expected:
        raise ValueError(f"{action}() requires status {expected.value}, got {experiment.status.value}")
