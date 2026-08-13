"""Adaptive planning (§7 of the build spec): PLAN -> OBSERVE -> REASSESS
-> ADAPT.

AdaptivePlanner.recommend() is a pure, deterministic function of its
inputs - same DailyIntent + same ReconciliationRecords in, same
PlanRecommendations out, mirroring every deterministic planner already on
this platform (ExecutivePlanner, every SpecialistPlanner). It never
applies a recommendation itself - every PlanRecommendation is returned to
the caller and requires the user's own authority to act on (§13),
consistent with "no autonomous action of any kind, anywhere on the
platform" (Product Philosophy Freeze).
"""

from dataclasses import dataclass

from app.services.personal_os.daily_intent import DailyIntent
from app.services.personal_os.reconciliation import ReconciliationRecord
from app.services.personal_os.shared.types import DayType, RecommendationKind, ReconciliationStatus


@dataclass(frozen=True)
class PlanRecommendation:
    """One suggested adaptation - never applied automatically. rationale
    cites the specific evidence (a ReconciliationRecord's own status,
    typically) that produced it, so a recommendation is never presented
    without a traceable reason."""

    kind: RecommendationKind
    subject: str
    rationale: str

    def __post_init__(self) -> None:
        if not self.subject:
            raise ValueError("PlanRecommendation.subject is required")
        if not self.rationale:
            raise ValueError("PlanRecommendation.rationale is required")


class AdaptivePlanner:
    """Deterministic recommendation generation from reconciled state.
    Holds no state of its own between calls - every recommend() call is
    independent and reproducible."""

    def recommend(
        self,
        intent: DailyIntent,
        reconciliations: tuple[ReconciliationRecord, ...],
    ) -> tuple[PlanRecommendation, ...]:
        if intent.is_rest_day or intent.day_type == DayType.REST:
            return (
                PlanRecommendation(
                    kind=RecommendationKind.PROTECT_REST,
                    subject="today",
                    rationale="Today's stated intent is a rest/recovery day - no carried-over "
                    "work is recommended for rescheduling into it.",
                ),
            )

        recommendations: list[PlanRecommendation] = []
        for record in reconciliations:
            recommendations.extend(self._recommendations_for(record))
        return tuple(recommendations)

    @staticmethod
    def _recommendations_for(record: ReconciliationRecord) -> tuple[PlanRecommendation, ...]:
        description = record.activity.description
        if record.status == ReconciliationStatus.BLOCKED:
            return (
                PlanRecommendation(
                    kind=RecommendationKind.MOVE,
                    subject=description,
                    rationale=f'"{description}" was reconciled as BLOCKED - recommend moving it '
                    "once the blocker is confirmed resolved, rather than re-planning it unchanged.",
                ),
            )
        if record.status == ReconciliationStatus.POSTPONED:
            return (
                PlanRecommendation(
                    kind=RecommendationKind.RESEQUENCE,
                    subject=description,
                    rationale=f'"{description}" was intentionally postponed - recommend '
                    "resequencing it into today's plan rather than treating it as newly added.",
                ),
            )
        if record.status == ReconciliationStatus.SUPERSEDED:
            return (
                PlanRecommendation(
                    kind=RecommendationKind.REPRIORITIZE,
                    subject=description,
                    rationale=f'"{description}" was superseded by "{record.evidence.superseding_priority}" - '
                    "recommend confirming whether it should be re-added at lower priority or dropped.",
                ),
            )
        if record.status == ReconciliationStatus.UNKNOWN:
            return (
                PlanRecommendation(
                    kind=RecommendationKind.ALLOCATE_MORE_TIME,
                    subject=description,
                    rationale=f'"{description}" has no recorded outcome - recommend asking for '
                    "evidence before reasoning about it further, never assuming it failed.",
                ),
            )
        return ()
