"""Adaptation (P7.10): the durable record of one controlled Learn /
Unlearn / Relearn cycle - "evidence supports a candidate update to
future Personal OS behavior or knowledge."

This is NOT a new learning engine and NOT a competing reasoning chain.
Adaptation composes what already exists, by reference, and owns only
what nothing else already owns:

- Evidence, pattern detection, confidence, and the proposed change
  itself all already live on Pattern/reasoning.py (`pattern_id` points
  there - a CONFIRMED Pattern with an attached GrowthRecommendation is
  a REQUIRED precondition for propose(), never re-derived or
  re-validated here).
- Measurement already lives on Experiment (`experiment_id`, optional -
  linked via adaptation_flow.link_experiment() once a real evaluation is
  run; Adaptation never computes its own baseline/comparison).
- What Adaptation owns, and nothing else in this package does: SCOPE
  (AdaptationTarget - which user/mission/workflow this affects, so an
  adaptation can never silently affect an unrelated one), a LIFECYCLE of
  its own (AdaptationStatus - distinct from Pattern's confirmation
  lifecycle and Experiment's measurement lifecycle; this is the
  lifecycle of a change actually being ADOPTED into how Personal OS
  behaves), and ADOPTION/ROLLBACK/SUPERSESSION identity that generalizes
  across all four scopes (`supersedes_adaptation_id` for RELEARN
  lineage, per P7.10 §8's own "preserve lineage where appropriate").

Governance boundary (P7.10 §10): AdaptationScope (shared/types.py) is a
closed enum with exactly four members - USER, USER_PREFERENCE, MISSION,
WORKFLOW. There is no scope value resembling authorization, security,
tenant isolation, tool permissions, or platform governance, so an
AdaptationTarget literally cannot be constructed to claim authority over
any of those - this is enforced by the type system, not by a runtime
check that could be bypassed, and independently verified by
test_personal_os_architecture.py.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.services.personal_os.shared.types import AdaptationEffectKind, AdaptationScope, AdaptationStatus, Confidence, LifeDomain, PriorityDirection

_LIFE_DOMAIN_VALUES = frozenset(domain.value for domain in LifeDomain)


@dataclass(frozen=True)
class AdaptationTarget:
    """WHERE an adaptation applies - a scope plus the specific entity
    within that scope (a mission_id for MISSION, a workflow name for
    WORKFLOW, str(user_id) for USER/USER_PREFERENCE). Never optional:
    P7.10 §9's own "must not silently affect unrelated users, missions,
    workflows" is enforced by making an unscoped Adaptation impossible to
    construct at all."""

    scope: AdaptationScope
    target_id: str

    def __post_init__(self) -> None:
        if not self.target_id:
            raise ValueError("AdaptationTarget.target_id is required - an adaptation must always be scoped, never global")


@dataclass(frozen=True)
class AdaptationEffect:
    """P7.11 - the explicit, structured runtime behavior an ADOPTED
    Adaptation carries. This is authored by whoever proposes the
    adaptation (a human or an agent acting on their behalf), never
    inferred at runtime from Pattern.pattern_type or from any prose on
    Pattern.recommendation.statement - PatternType describes what was
    OBSERVED, not what Personal OS should DO about it, and those two
    remain deliberately distinct (see this module's own docstring on
    why Adaptation composes Pattern by reference rather than reusing its
    fields for a second purpose).

    Bounded and closed by construction: `kind` is one of
    AdaptationEffectKind's named members (never a free-form string a
    consumer pattern-matches on), and `direction` is one of two named
    values whose actual magnitude is owned entirely by
    PriorityConfig.adaptation_priority_boost - never a per-adaptation
    numeric value an adopted preference could author large enough to
    overwhelm the deterministic Priority Engine."""

    kind: AdaptationEffectKind
    direction: PriorityDirection


@dataclass(frozen=True)
class Adaptation:
    """Everything P7.10 §5/§11 requires, at minimum, composed rather
    than duplicated: `pattern_id` is where the observation, evidence,
    hypothesis, and proposed change itself all already live
    (`Pattern.recommendation.statement` IS "what change is proposed";
    `Pattern.recommendation.responds_to.statement` IS "why"; nothing
    here re-states them). `confidence` is a snapshot of the underlying
    Pattern's own confidence at the moment this Adaptation was proposed
    (mirroring `Experiment.baseline` being a snapshot, not a live
    pointer) - never a second, independently-computed score.
    `expected_outcome` is the one genuinely new piece of content this
    type owns: "what evidence would confirm success," for the case
    where no Experiment has been linked yet (§11's own "what evidence
    would confirm success / invalidate it," ahead of Experiment's own,
    more precise `measurement_plan` once one exists)."""

    adaptation_id: str
    target: AdaptationTarget
    pattern_id: str
    confidence: Confidence
    expected_outcome: str = ""
    experiment_id: str | None = None
    status: AdaptationStatus = AdaptationStatus.PROPOSED
    supersedes_adaptation_id: str | None = None
    decision_reason: str = ""
    effect: AdaptationEffect | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.pattern_id:
            raise ValueError("Adaptation.pattern_id is required - an adaptation must always be evidence-backed by a real Pattern")
        if (
            self.effect is not None
            and self.effect.kind == AdaptationEffectKind.PRIORITY_ADJUSTMENT
            and self.target.scope == AdaptationScope.USER_PREFERENCE
            and self.target.target_id not in _LIFE_DOMAIN_VALUES
        ):
            raise ValueError(
                "A USER_PREFERENCE PRIORITY_ADJUSTMENT effect requires target.target_id to be an "
                "existing LifeDomain value - that is the only stable, structured identifier the "
                "Priority Engine can match a preference against; there is no fuzzy-matching fallback"
            )
