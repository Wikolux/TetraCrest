"""Delivery Specialist structured outputs (Milestone 5) - mirrors
Discovery's/Product Decision's own outputs.py precedent exactly
(Milestones 3-4): every type here is a synthesis/response-shaping
structure, never a memory type of its own. "Decision Record" and "PM
Craft Record" are Milestones 1 and 4's own types, read here, never
redefined; "Delivery Artifact" is this milestone's memory-backed type
(shared/delivery_artifact.py), also not redefined here.

`DeliveryConfidenceScore` is this milestone's approved architectural
enhancement: every major delivery recommendation exposes a score that
*explains itself* - which concrete factors were satisfied and which were
missing - never a bare, unexplained number. It is deliberately computed
as a simple, deterministic fraction of checkable factors (see
confidence.py), not a model-generated probability: "explanatory, not
probabilistic AI confidence," per this milestone's own governing
instruction, and consistent with the platform-wide "deterministic, not
adaptive" discipline every planner already follows.
"""

from dataclasses import dataclass, field


def _as_tuple(value) -> tuple:
    return value if isinstance(value, tuple) else tuple(value)


@dataclass(frozen=True)
class ConfidenceFactor:
    label: str
    satisfied: bool
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("ConfidenceFactor.label is required")


@dataclass(frozen=True)
class DeliveryConfidenceScore:
    score_percent: int
    factors: tuple[ConfidenceFactor, ...]

    def __post_init__(self) -> None:
        if not 0 <= self.score_percent <= 100:
            raise ValueError("DeliveryConfidenceScore.score_percent must be between 0 and 100")
        object.__setattr__(self, "factors", _as_tuple(self.factors))
        if not self.factors:
            raise ValueError("DeliveryConfidenceScore.factors must not be empty - a score must explain itself")

    @property
    def supporting(self) -> tuple[ConfidenceFactor, ...]:
        return tuple(factor for factor in self.factors if factor.satisfied)

    @property
    def missing(self) -> tuple[ConfidenceFactor, ...]:
        return tuple(factor for factor in self.factors if not factor.satisfied)


@dataclass(frozen=True)
class SprintPlan:
    sprint_goal: str
    items: tuple[str, ...] = field(default_factory=tuple)
    capacity_note: str = ""
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.sprint_goal:
            raise ValueError("SprintPlan.sprint_goal is required")
        object.__setattr__(self, "items", _as_tuple(self.items))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))


@dataclass(frozen=True)
class StoryBreakdown:
    parent: str
    stories: tuple[str, ...]
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.parent:
            raise ValueError("StoryBreakdown.parent is required")
        object.__setattr__(self, "stories", _as_tuple(self.stories))
        if not self.stories:
            raise ValueError("StoryBreakdown.stories must not be empty")
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))


@dataclass(frozen=True)
class EpicPlan:
    epic_title: str
    stories: tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.epic_title:
            raise ValueError("EpicPlan.epic_title is required")
        object.__setattr__(self, "stories", _as_tuple(self.stories))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))


@dataclass(frozen=True)
class DependencyItem:
    name: str
    mentioned_in_evidence: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("DependencyItem.name is required")


@dataclass(frozen=True)
class DependencyMap:
    dependencies: tuple[DependencyItem, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "dependencies", _as_tuple(self.dependencies))
        if not self.dependencies:
            raise ValueError("DependencyMap.dependencies must not be empty")


@dataclass(frozen=True)
class DeliveryRiskItem:
    description: str
    likelihood: str = "unknown"

    def __post_init__(self) -> None:
        if not self.description:
            raise ValueError("DeliveryRiskItem.description is required")


@dataclass(frozen=True)
class DeliveryRiskReport:
    risks: tuple[DeliveryRiskItem, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "risks", _as_tuple(self.risks))
        if not self.risks:
            raise ValueError("DeliveryRiskReport.risks must not be empty")


@dataclass(frozen=True)
class DeliveryRecommendation:
    recommendation: str
    confidence: DeliveryConfidenceScore
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_gap: str = ""

    def __post_init__(self) -> None:
        if not self.recommendation:
            raise ValueError("DeliveryRecommendation.recommendation is required")
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        if not self.evidence_ids and not self.evidence_gap:
            raise ValueError(
                "DeliveryRecommendation must cite supporting evidence_ids or state an explicit "
                "evidence_gap - a recommendation may never be silently ungrounded"
            )


@dataclass(frozen=True)
class SprintSummary:
    summary: str
    artifact_count: int = 0
    feature_count: int = 0


@dataclass(frozen=True)
class RetrospectiveSummary:
    summary: str
    planned: tuple[str, ...] = field(default_factory=tuple)
    actual: tuple[str, ...] = field(default_factory=tuple)
    gaps: tuple[str, ...] = field(default_factory=tuple)
    surprises: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.summary:
            raise ValueError("RetrospectiveSummary.summary is required")
        for name in ("planned", "actual", "gaps", "surprises"):
            object.__setattr__(self, name, _as_tuple(getattr(self, name)))
