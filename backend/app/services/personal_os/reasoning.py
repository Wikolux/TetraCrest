"""Reflection & growth reasoning artifacts (§10 of the P1 build spec;
extended in P2 §4 with UserExplanation): structurally distinguishing an
observed fact from an inferred pattern from a user's own explanation from
a system hypothesis from a recommendation, so inference is never
presented as fact and a user's own account is never presented as a
system judgment.

Mirrors CP-01.3's InsightEngine precedent exactly - basis is a required,
non-optional field on every artifact, and an InferredPattern/Hypothesis
cannot be constructed without the ObservedFact(s) it was derived from,
the same "supporting_memory_ids required at construction" discipline
Insight already proved out for this platform.
"""

from dataclasses import dataclass, field

from app.services.personal_os.shared.types import ObservationBasis


@dataclass(frozen=True)
class ObservedFact:
    """Something Personal OS directly recorded - a ReconciliationRecord's
    status, a stated deadline, a count. Never itself an interpretation."""

    statement: str
    evidence_ref: str = ""

    def __post_init__(self) -> None:
        if not self.statement:
            raise ValueError("ObservedFact.statement is required")


@dataclass(frozen=True)
class InferredPattern:
    """A pattern noticed across two or more ObservedFacts - cannot be
    constructed from fewer than two, since "a pattern" of one observation
    is just the observation itself, not a pattern."""

    statement: str
    basis: ObservationBasis = field(default=ObservationBasis.INFERRED_PATTERN, init=False)
    supporting_facts: tuple[ObservedFact, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.statement:
            raise ValueError("InferredPattern.statement is required")
        if not isinstance(self.supporting_facts, tuple):
            object.__setattr__(self, "supporting_facts", tuple(self.supporting_facts))
        if len(self.supporting_facts) < 2:
            raise ValueError(
                "InferredPattern requires at least two supporting_facts - a single observation is a fact, not a pattern"
            )


@dataclass(frozen=True)
class UserExplanation:
    """A reason the user themselves gave for something (P2 §4) - never
    itself a fact (it is the user's own interpretation, even when true)
    and never a system Hypothesis (it did not originate with Personal
    OS's own reasoning). Kept structurally separate so a later Hypothesis
    can cite it without the two ever being conflated into one claim."""

    statement: str
    basis: ObservationBasis = field(default=ObservationBasis.USER_EXPLANATION, init=False)
    explains_activity: str = ""

    def __post_init__(self) -> None:
        if not self.statement:
            raise ValueError("UserExplanation.statement is required")


@dataclass(frozen=True)
class Hypothesis:
    """A candidate explanation for an InferredPattern - explicitly
    tentative (the "may indicate" framing from §10's own worked example),
    never asserted as settled. Cannot be constructed without the pattern
    it explains.

    informed_by (P2) is optional: a Hypothesis grounded in the user's own
    stated UserExplanation(s) is more evidenced than a bare system guess,
    and this field is how that distinction stays visible - never required,
    since a hypothesis can legitimately exist with no explanation offered
    (the user simply wasn't asked, or didn't say)."""

    statement: str
    basis: ObservationBasis = field(default=ObservationBasis.HYPOTHESIS, init=False)
    explains: InferredPattern | None = None
    informed_by: tuple[UserExplanation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.statement:
            raise ValueError("Hypothesis.statement is required")
        if self.explains is None:
            raise ValueError("Hypothesis.explains is required - a hypothesis must explain a specific InferredPattern")
        if not isinstance(self.informed_by, tuple):
            object.__setattr__(self, "informed_by", tuple(self.informed_by))


@dataclass(frozen=True)
class GrowthRecommendation:
    """What Personal OS suggests doing about a Hypothesis - always a
    recommendation the user can accept or ignore, never an instruction,
    matching the platform-wide "recommendations remain recommendations"
    rule (§7, §13)."""

    statement: str
    basis: ObservationBasis = field(default=ObservationBasis.RECOMMENDATION, init=False)
    responds_to: Hypothesis | None = None

    def __post_init__(self) -> None:
        if not self.statement:
            raise ValueError("GrowthRecommendation.statement is required")
        if self.responds_to is None:
            raise ValueError("GrowthRecommendation.responds_to is required - a recommendation must respond to a Hypothesis")
