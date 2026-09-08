"""AdaptationOutcomeFlow (P7.12): closes the loop P7.11 left open at
"behavior changed" - determining whether an ADOPTED Adaptation's runtime
effect actually helped, by reusing the Experiment system's own
baseline/measurement/comparison/review machinery entirely as-is. Never
a second measurement engine, never an `AdaptationMeasurement`/
`AdaptationComparison` type: Experiment already owns measurement,
Pattern already owns evidence, Adaptation owns the approved change - this
flow only wires the three together for one new question none of them
individually answers.

Two responsibilities, matching every other Personal OS `*_flow.py`'s own
"thin orchestration, never re-implement the deterministic core"
discipline exactly:

1. `propose_outcome_experiment()` - builds ONE new, real, evidence-backed
   Experiment via the EXISTING `PatternDetectionFlow.propose_experiment()`
   (unchanged), computing the post-adoption boundary from the Adaptation's
   own durable history (`adaptation_outcome.py`) so the caller cannot
   accidentally leak pre-adoption evidence into `started_on` - then links
   it via the new, narrowly-scoped
   `AdaptationFlow.link_outcome_experiment()`.
2. `review_outcome()` - runs `ExperimentFlow.review()` (unchanged)
   against that linked Experiment, and reports whether the measured
   Adaptation is STILL the currently adopted one, plus a plain,
   non-binding recommendation - never itself calling
   `ExperimentFlow.decide()`, `AdaptationFlow.rollback()`, or
   `AdaptationFlow.propose_relearn()`. This flow observes, measures, and
   recommends; it never decides on the user's behalf (Product Philosophy
   Freeze §5).
"""

from datetime import date

from app.services.personal_os.adaptation import Adaptation
from app.services.personal_os.adaptation_flow import AdaptationFlow
from app.services.personal_os.adaptation_outcome import AdaptationOutcomeReview, earliest_measurable_start, recommend_next_step, resolve_adopted_at
from app.services.personal_os.adaptation_repository import AdaptationRepository
from app.services.personal_os.experiment_flow import ExperimentFlow
from app.services.personal_os.experiment_repository import ExperimentRepository
from app.services.personal_os.pattern import Pattern
from app.services.personal_os.pattern_evidence import EvidenceWindow
from app.services.personal_os.pattern_flow import PatternDetectionFlow
from app.services.personal_os.shared.types import AdaptationStatus, ExperimentOutcome


class AdaptationOutcomeFlow:
    def __init__(
        self,
        adaptation_repository: AdaptationRepository,
        adaptation_flow: AdaptationFlow,
        pattern_flow: PatternDetectionFlow,
        experiment_flow: ExperimentFlow,
        experiment_repository: ExperimentRepository,
    ) -> None:
        self.adaptation_repository = adaptation_repository
        self.adaptation_flow = adaptation_flow
        self.pattern_flow = pattern_flow
        self.experiment_flow = experiment_flow
        self.experiment_repository = experiment_repository

    def propose_outcome_experiment(
        self,
        adaptation: Adaptation,
        *,
        organization_id: int,
        user_id: int,
        pattern: Pattern,
        hypothesis_statement: str,
        adjustment: str,
        measurement_plan: str,
        metric: str,
        category: str,
        baseline_window: EvidenceWindow,
        review_date: date | None = None,
    ) -> Adaptation:
        """Builds a real, evidence-backed pre-adoption baseline from
        `baseline_window` via the EXACT existing
        `PatternDetectionFlow.propose_experiment()` (never recomputing
        baseline machinery itself - see experiment_measurement.py), then
        links the result to `adaptation` via
        `AdaptationFlow.link_outcome_experiment()`.

        `started_on` is deliberately NOT a caller parameter here: it is
        derived from the Adaptation's own ADOPTED transition
        (link_outcome_experiment()'s own temporal guarantee), removing
        an entire class of caller error rather than merely documenting
        the correct value. `baseline_window` must end at or before the
        adoption day - never later - since a "before" picture built
        from evidence that happened after the change is not a baseline
        at all (§6).

        Also drives the new Experiment through approve()/activate() -
        both plain, non-consequential bookkeeping transitions (an
        Experiment's own status never itself changes Personal OS
        behavior; only an ADOPTED Adaptation does that, via P7.11's
        separate, already-governed runtime wiring), unlike
        AdaptationFlow's own approve()/adopt()/rollback(), which stay
        exactly as human-governed as P7.10 built them. `activate()` is
        given `started_on` (not "today") as its own `today` argument
        specifically, since activate() otherwise stamps `started_on`
        from whenever it happens to be CALLED - passing the already-
        computed boundary through explicitly is what keeps this correct
        even when propose_outcome_experiment() is itself invoked well
        after the boundary date."""
        if adaptation.status != AdaptationStatus.ADOPTED:
            raise ValueError("propose_outcome_experiment() requires an ADOPTED adaptation - there is nothing to measure the outcome of otherwise")
        if pattern.pattern_id != adaptation.pattern_id:
            raise ValueError("propose_outcome_experiment() requires a pattern matching this adaptation's own pattern_id")

        history = self.adaptation_repository.get_history(organization_id=organization_id, user_id=user_id, adaptation_id=adaptation.adaptation_id)
        adopted_at = resolve_adopted_at(history)
        if adopted_at is None:
            raise ValueError("propose_outcome_experiment() found no ADOPTED version in this adaptation's history")

        started_on = earliest_measurable_start(adopted_at)
        if baseline_window.end >= started_on:
            raise ValueError(
                f"baseline_window must end before the post-adoption boundary ({started_on}) - a pre-change "
                "baseline cannot include post-adoption evidence"
            )

        experiment = self.pattern_flow.propose_experiment(
            pattern,
            organization_id=organization_id,
            user_id=user_id,
            hypothesis_statement=hypothesis_statement,
            adjustment=adjustment,
            measurement_plan=measurement_plan,
            metric=metric,
            category=category,
            baseline_window=baseline_window,
            started_on=started_on,
            review_date=review_date,
        )
        experiment = self.experiment_flow.approve(organization_id=organization_id, user_id=user_id, experiment=experiment)
        experiment = self.experiment_flow.activate(organization_id=organization_id, user_id=user_id, experiment=experiment, today=started_on)
        return self.adaptation_flow.link_outcome_experiment(adaptation, organization_id=organization_id, user_id=user_id, experiment=experiment)

    def review_outcome(
        self,
        adaptation: Adaptation,
        *,
        organization_id: int,
        user_id: int,
        today: date,
        conversation_id: int | None = None,
    ) -> AdaptationOutcomeReview:
        """Runs the EXISTING `ExperimentFlow.review()` against the
        linked outcome experiment - never recomputes measurement or
        comparison itself - and reports whether the measured Adaptation
        is STILL the currently adopted one, so a rolled-back or
        superseded Adaptation's own historical measurement is never
        presented as evidence about a currently active preference (never
        silently transferred to whatever superseded it, either - this
        reports on `adaptation` alone)."""
        if adaptation.outcome_experiment_id is None:
            raise ValueError("review_outcome() requires an adaptation with a linked outcome experiment - call propose_outcome_experiment() first")

        experiment = self.experiment_repository.get_latest(
            organization_id=organization_id, user_id=user_id, experiment_id=adaptation.outcome_experiment_id
        )
        if experiment is None:
            raise ValueError(f"review_outcome() could not find outcome experiment {adaptation.outcome_experiment_id!r}")

        reviewed = self.experiment_flow.review(
            organization_id=organization_id, user_id=user_id, experiment=experiment, today=today, conversation_id=conversation_id
        )

        current = self.adaptation_repository.get_latest(organization_id=organization_id, user_id=user_id, adaptation_id=adaptation.adaptation_id)
        current_status = current.status if current is not None else adaptation.status
        is_currently_adopted = current_status == AdaptationStatus.ADOPTED

        # review() always sets `comparison` (build_measurement() never refuses to construct, unlike
        # build_baseline() - see experiment_measurement.py's own docstring); the INSUFFICIENT_DATA
        # fallback below is an honest guard against that assumption ever changing, not a real path today.
        outcome = reviewed.comparison.outcome if reviewed.comparison is not None else ExperimentOutcome.INSUFFICIENT_DATA
        recommendation = recommend_next_step(outcome)
        if not is_currently_adopted:
            recommendation = (
                f"This adaptation is no longer currently adopted (status: {current_status.value}) - this "
                f"measurement is historical only and should not be read as evidence about an active preference. {recommendation}"
            )

        return AdaptationOutcomeReview(
            experiment=reviewed, adaptation_status=current_status, is_currently_adopted=is_currently_adopted, recommendation=recommendation
        )
