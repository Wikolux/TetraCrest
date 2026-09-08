"""AdaptationFlow (P7.10): the controlled orchestration connecting
already-existing Pattern -> Hypothesis -> GrowthRecommendation ->
Experiment machinery into a governed Learn / Unlearn / Relearn lifecycle.

Not a second learning engine: every method here is a thin state
transition over the Adaptation record (adaptation.py) plus, where
genuinely needed, a lookup into PatternRepository/ExperimentRepository -
never a re-implementation of pattern detection, evidence gathering, or
measurement, all of which already exist and are reused as-is.

The OS recommends; it never adopts on its own. Every transition in this
class requires an explicit caller (the human, via whatever surface
eventually calls this flow) - nothing here auto-approves, auto-adopts,
or auto-rolls-back based on a measured outcome. present() may explain a
result in natural language; it is never the thing that decides one
(mirrors pattern_flow.py's/experiment_flow.py's own "compute first,
narrate second" discipline exactly).
"""

from dataclasses import replace
from datetime import UTC, datetime

from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.types import RuntimeRequest
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.context.types import ContextItem, ContextPackage, ContextSection
from app.services.prompt_builder.builder import PromptBuilder
from app.services.personal_os.adaptation import Adaptation, AdaptationEffect, AdaptationTarget
from app.services.personal_os.adaptation_outcome import earliest_measurable_start, resolve_adopted_at
from app.services.personal_os.adaptation_repository import AdaptationRepository
from app.services.personal_os.experiment import Experiment
from app.services.personal_os.pattern import Pattern
from app.services.personal_os.shared.types import AdaptationStatus, ExperimentOutcome, PatternStatus


class AdaptationFlow:
    def __init__(
        self,
        adaptation_repository: AdaptationRepository,
        runtime_adapter: RuntimeAdapter | None = None,
        default_provider: ProviderName = ProviderName.OPENAI,
    ) -> None:
        self.adaptation_repository = adaptation_repository
        self.runtime_adapter = runtime_adapter or RuntimeAdapter()
        self.default_provider = default_provider

    # --- LEARN (§6) / RELEARN (§8): propose -------------------------------------------------------

    def propose(
        self,
        pattern: Pattern,
        *,
        organization_id: int,
        user_id: int,
        target: AdaptationTarget,
        expected_outcome: str = "",
        effect: AdaptationEffect | None = None,
    ) -> Adaptation:
        """§6: evidence -> pattern -> candidate. Requires a CONFIRMED
        pattern with an attached recommendation - the identical evidence
        gate pattern_flow.attach_recommendation() already established
        ("a recommendation responding to a pattern the user rejected or
        hasn't yet confirmed would be advice built on nothing the user
        actually agreed happened") - never a single unverified
        observation becoming a proposal (§ Evidence Requirement).

        `effect` (P7.11, optional) is the explicit, structured runtime
        behavior this proposal asks to adopt - authored by the caller
        (the human, or an agent acting on their explicit behalf) at
        proposal time, exactly like `expected_outcome`; never derived
        from `pattern.pattern_type` or `pattern.recommendation.statement`
        here or anywhere downstream (see AdaptationEffect's own
        docstring). Omitting it produces a purely advisory Adaptation
        with no runtime-consumable effect, unchanged from P7.10.

        Idempotent (§16): a second proposal for the same pattern and the
        same target while an active one already exists returns the
        existing Adaptation unchanged, rather than creating a duplicate -
        deterministic behavior for duplicate proposals, no locking
        infrastructure required."""
        self._require_evidence(pattern)

        existing = self._find_active_for(organization_id, user_id, pattern.pattern_id, target)
        if existing is not None:
            return existing

        adaptation = Adaptation(
            adaptation_id="",
            target=target,
            pattern_id=pattern.pattern_id,
            confidence=pattern.confidence,
            expected_outcome=expected_outcome,
            status=AdaptationStatus.PROPOSED,
            effect=effect,
        )
        return self.adaptation_repository.save(adaptation, organization_id=organization_id, user_id=user_id)

    def propose_relearn(
        self,
        pattern: Pattern,
        *,
        organization_id: int,
        user_id: int,
        supersedes: Adaptation,
        expected_outcome: str = "",
        effect: AdaptationEffect | None = None,
    ) -> Adaptation:
        """§8: a new hypothesis, evidenced by new/contradictory Pattern
        evidence, proposed as a replacement for an already-ADOPTED
        adaptation - lineage preserved via supersedes_adaptation_id;
        the predecessor is only actually superseded once THIS proposal
        is itself adopted (adopt() below), never the moment it is merely
        proposed. `effect` (P7.11, optional) follows propose()'s own
        rule exactly - the caller's explicit statement of the new
        runtime behavior, defaulting to none."""
        self._require_evidence(pattern)
        if supersedes.status != AdaptationStatus.ADOPTED:
            raise ValueError("propose_relearn() requires superseding an ADOPTED adaptation")

        existing = self._find_active_for(organization_id, user_id, pattern.pattern_id, supersedes.target)
        if existing is not None:
            return existing

        adaptation = Adaptation(
            adaptation_id="",
            target=supersedes.target,
            pattern_id=pattern.pattern_id,
            confidence=pattern.confidence,
            expected_outcome=expected_outcome,
            status=AdaptationStatus.PROPOSED,
            supersedes_adaptation_id=supersedes.adaptation_id,
            effect=effect,
        )
        return self.adaptation_repository.save(adaptation, organization_id=organization_id, user_id=user_id)

    # --- evaluation / measurement (§14) ------------------------------------------------------------

    def begin_evaluation(self, adaptation: Adaptation, *, organization_id: int, user_id: int) -> Adaptation:
        _require_status(adaptation, AdaptationStatus.PROPOSED, "begin_evaluation")
        return self._save(organization_id, user_id, replace(adaptation, status=AdaptationStatus.UNDER_EVALUATION))

    def link_experiment(self, adaptation: Adaptation, *, organization_id: int, user_id: int, experiment: Experiment) -> Adaptation:
        """Optional - only when a real, measured evaluation is actually
        run. Reuses Experiment's own baseline/measurement/comparison
        machinery entirely as-is; this method only stores the reference,
        never re-computes or duplicates any of it."""
        _require_status(adaptation, AdaptationStatus.UNDER_EVALUATION, "link_experiment")
        if experiment.pattern_id != adaptation.pattern_id:
            raise ValueError("link_experiment() requires an experiment measuring the same pattern this adaptation is based on")
        return self._save(organization_id, user_id, replace(adaptation, experiment_id=experiment.experiment_id))

    # --- post-adoption outcome measurement (P7.12) -------------------------------------------------

    def link_outcome_experiment(self, adaptation: Adaptation, *, organization_id: int, user_id: int, experiment: Experiment) -> Adaptation:
        """P7.12: the explicit, durable relationship between an ADOPTED
        Adaptation and the Experiment measuring what happened AFTER it
        was adopted - deliberately a SEPARATE field from `experiment_id`,
        never overloaded: `experiment_id` (above) means the pre-adoption
        evaluation that informed the approve()/adopt() decision -
        `link_experiment()`'s own UNDER_EVALUATION gate makes that
        meaning structural, not just documented. Reusing that same field
        for a second, later Experiment answering a different question
        ("did the adopted change help?") would make one field mean two
        different things depending on when it was set - so
        `outcome_experiment_id` exists instead, gated the other way
        (requires ADOPTED, since there is nothing to measure the outcome
        of before then).

        Requires the same pattern_id match `link_experiment()` already
        requires, plus the one guarantee P7.12 exists for: this
        Experiment's own `started_on` must fall on or after the day
        immediately following this Adaptation's own ADOPTED transition
        (resolve_adopted_at()/earliest_measurable_start(),
        adaptation_outcome.py) - enforced HERE, structurally, regardless
        of how the Experiment was constructed or by which caller, so
        pre-adoption evidence can never be counted as this Adaptation's
        own post-adoption result."""
        _require_status(adaptation, AdaptationStatus.ADOPTED, "link_outcome_experiment")
        if experiment.pattern_id != adaptation.pattern_id:
            raise ValueError("link_outcome_experiment() requires an experiment measuring the same pattern this adaptation is based on")

        history = self.adaptation_repository.get_history(organization_id=organization_id, user_id=user_id, adaptation_id=adaptation.adaptation_id)
        adopted_at = resolve_adopted_at(history)
        if adopted_at is None:
            raise ValueError("link_outcome_experiment() requires this adaptation to have an ADOPTED version in its own history")

        earliest_start = earliest_measurable_start(adopted_at)
        if experiment.started_on < earliest_start:
            raise ValueError(
                f"link_outcome_experiment() requires experiment.started_on >= {earliest_start} (the day after "
                f"adoption), got {experiment.started_on} - pre-adoption evidence must never be counted as this "
                "adaptation's own post-adoption result"
            )

        return self._save(organization_id, user_id, replace(adaptation, outcome_experiment_id=experiment.experiment_id))

    @staticmethod
    def measured_outcome(experiment: Experiment | None) -> ExperimentOutcome | None:
        """A read-only surface for whatever the linked Experiment (if
        any) has measured so far - informs a human's approve()/adopt()/
        rollback() decision, never substitutes for it (§14: adoption is
        never automatic based on a measured outcome)."""
        if experiment is None or experiment.comparison is None:
            return None
        return experiment.comparison.outcome

    # --- approval boundary (§12) -------------------------------------------------------------------

    def approve(self, adaptation: Adaptation, *, organization_id: int, user_id: int, reason: str = "") -> Adaptation:
        """The explicit human-approval gate (Product Philosophy Freeze
        §5: "consequential action is never taken... without them
        deliberately saying yes first") - mirrors Experiment's own
        approve()/reject() precedent exactly. Callable from PROPOSED
        directly (evaluation is optional, not mandatory) or from
        UNDER_EVALUATION."""
        if adaptation.status not in (AdaptationStatus.PROPOSED, AdaptationStatus.UNDER_EVALUATION):
            raise ValueError(f"approve() requires PROPOSED or UNDER_EVALUATION, got {adaptation.status.value}")
        return self._save(organization_id, user_id, replace(adaptation, status=AdaptationStatus.APPROVED, decision_reason=reason))

    def reject(self, adaptation: Adaptation, *, organization_id: int, user_id: int, reason: str) -> Adaptation:
        """§4/§12: "rejected proposals do not alter active behavior" -
        REJECTED is terminal; nothing about this Adaptation is ever
        adopted, and it is never resurfaced as if unresolved."""
        if not reason:
            raise ValueError("reject() requires a reason")
        if adaptation.status not in (AdaptationStatus.PROPOSED, AdaptationStatus.UNDER_EVALUATION, AdaptationStatus.APPROVED):
            raise ValueError(f"reject() cannot be called on a terminal or already-adopted adaptation (status={adaptation.status.value})")
        return self._save(organization_id, user_id, replace(adaptation, status=AdaptationStatus.REJECTED, decision_reason=reason))

    # --- adoption (§12) ------------------------------------------------------------------------------

    def adopt(self, adaptation: Adaptation, *, organization_id: int, user_id: int) -> Adaptation:
        """§12: "adopted/approved changes must only affect their
        authorized scope." If this Adaptation is a RELEARN
        (supersedes_adaptation_id set), the predecessor is transitioned
        to SUPERSEDED in the same call - preserving its own full history
        (§8's "preserve lineage"), never deleting or rewriting it. This
        keeps get_adopted_for_target() honest: never more than one
        ADOPTED adaptation per target."""
        _require_status(adaptation, AdaptationStatus.APPROVED, "adopt")
        adopted = self._save(organization_id, user_id, replace(adaptation, status=AdaptationStatus.ADOPTED))

        if adaptation.supersedes_adaptation_id:
            predecessor = self.adaptation_repository.get_latest(
                organization_id=organization_id, user_id=user_id, adaptation_id=adaptation.supersedes_adaptation_id
            )
            if predecessor is not None and predecessor.status == AdaptationStatus.ADOPTED:
                self._save(organization_id, user_id, replace(predecessor, status=AdaptationStatus.SUPERSEDED))

        return adopted

    # --- rollback / unlearn (§7, §13) -------------------------------------------------------------------

    def rollback(self, adaptation: Adaptation, *, organization_id: int, user_id: int, reason: str) -> Adaptation:
        """§13: "rollback should restore the previous valid state where
        technically possible... do not rewrite history." This method
        only marks the adaptation ROLLED_BACK - restoring whatever
        Personal OS surface actually reads get_adopted_for_target() to
        its prior behavior is that surface's own responsibility, since
        this module owns the adaptation record, not the behavior it
        informs."""
        if not reason:
            raise ValueError("rollback() requires a reason")
        _require_status(adaptation, AdaptationStatus.ADOPTED, "rollback")
        return self._save(organization_id, user_id, replace(adaptation, status=AdaptationStatus.ROLLED_BACK, decision_reason=reason))

    def retire(self, adaptation: Adaptation, *, organization_id: int, user_id: int, reason: str) -> Adaptation:
        """§7: pure UNLEARN - no replacement. Marks an ADOPTED adaptation
        obsolete without a new hypothesis taking its place (contrast
        with propose_relearn()+adopt(), which supersedes WITH a
        replacement). The historical record is preserved exactly like
        ROLLED_BACK/SUPERSEDED - only its status changes, never its
        content."""
        if not reason:
            raise ValueError("retire() requires a reason")
        _require_status(adaptation, AdaptationStatus.ADOPTED, "retire")
        return self._save(organization_id, user_id, replace(adaptation, status=AdaptationStatus.SUPERSEDED, decision_reason=reason))

    # --- queries --------------------------------------------------------------------------------------

    def get_adopted(self, *, organization_id: int, user_id: int, target: AdaptationTarget) -> Adaptation | None:
        return self.adaptation_repository.get_adopted_for_target(organization_id=organization_id, user_id=user_id, target=target)

    # --- narration (the one generative step) -----------------------------------------------------------

    def present(self, adaptation: Adaptation, pattern: Pattern, *, organization_id: int, conversation_id: int | None = None) -> str:
        """The one real Runtime integration point in this flow - mirrors
        pattern_flow.py's/experiment_flow.py's/priority_flow.py's own
        _narrate() exactly. The proposed change, its evidence, and its
        rationale are all already decided (they live on `pattern`, read
        only, never altered here); the Runtime only phrases them for a
        human to review before approve()/reject()."""
        statement = pattern.recommendation.statement if pattern.recommendation else pattern.pattern_statement
        rationale = ""
        if pattern.recommendation and pattern.recommendation.responds_to:
            rationale = pattern.recommendation.responds_to.statement

        package = ContextPackage(
            sections=[
                ContextSection(
                    resource_type="adaptation",
                    items=[
                        ContextItem(
                            resource_type="adaptation",
                            resource_id=0,
                            content=f"{statement} {rationale}".strip(),
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
            f"Explain, in 1-2 short sentences, this proposed adaptation for {adaptation.target.scope.value} "
            f'"{adaptation.target.target_id}": {statement} {rationale} '
            "State this as a proposal awaiting the user's own approval, never as something already decided or already in effect."
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
        fallback = f"Proposed change: {statement}"
        if rationale:
            fallback += f" Rationale: {rationale}"
        return fallback

    # --- internals ---------------------------------------------------------------------------------------

    def _save(self, organization_id: int, user_id: int, adaptation: Adaptation) -> Adaptation:
        updated = replace(adaptation, updated_at=datetime.now(UTC))
        return self.adaptation_repository.save(updated, organization_id=organization_id, user_id=user_id)

    def _find_active_for(self, organization_id: int, user_id: int, pattern_id: str, target: AdaptationTarget) -> Adaptation | None:
        for existing in self.adaptation_repository.list_active(organization_id=organization_id, user_id=user_id):
            if existing.pattern_id == pattern_id and existing.target == target:
                return existing
        return None

    @staticmethod
    def _require_evidence(pattern: Pattern) -> None:
        if pattern.status != PatternStatus.CONFIRMED:
            raise ValueError("propose() requires a CONFIRMED pattern - adaptation must be evidence-backed, never built from an unconfirmed observation")
        if pattern.recommendation is None:
            raise ValueError("propose() requires a pattern with an attached recommendation - there is nothing to adopt without one")


def _require_status(adaptation: Adaptation, expected: AdaptationStatus, action: str) -> None:
    if adaptation.status != expected:
        raise ValueError(f"{action}() requires status {expected.value}, got {adaptation.status.value}")
