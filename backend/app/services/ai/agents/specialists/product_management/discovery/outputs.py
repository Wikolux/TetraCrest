"""Discovery Specialist structured outputs (Milestone 3) - the ten output
shapes the milestone's own task list names (Discovery Summary, Discovery
Recommendation, Interview Summary, Interview Insights, JTBD Analysis,
Problem Statement, Persona Summary, Hypothesis List, Opportunity List,
Discovery Report).

None of these is a memory type or a new storage mechanism - they play the
identical architectural role ResearchReport (app.services.ai.agents.specialists.research.report)
already plays for ResearchAgent: an in-process synthesis/response-shaping
structure, rendered into a SpecialistResponse and, where the content
constitutes durable evidence, converted into an already-approved Milestone
1 domain object (DiscoveryFinding, ResearchFinding) for storage through
ProfessionalMemoryService. No eleventh memory category is introduced here
or anywhere in this milestone.

Evidence discipline is enforced structurally, not by convention, mirroring
the pattern ARR §7 requires (the same discipline CP-01.3's `Insight` type
and Milestone 1's `DiscoveryFinding`/`ResearchFinding`/`DecisionRecord`
already prove out): a type that could otherwise carry a fabricated,
unsupported conclusion is simply impossible to construct in that state.
`DiscoveryRecommendation` is the sharpest instance of this - it cannot be
built without either citing supporting evidence or stating an explicit
evidence gap, so "no fabricated conclusions" (this milestone's own
requirement) is a property of the type, not a hope about the prompt.
"""

from dataclasses import dataclass, field

from app.services.ai.agents.specialists.product_management.shared.discovery_finding import HypothesisStatus


def _as_tuple(value) -> tuple:
    return value if isinstance(value, tuple) else tuple(value)


@dataclass(frozen=True)
class ProblemStatement:
    statement: str
    target_segment: str = ""
    validated: bool = False
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.statement:
            raise ValueError("ProblemStatement.statement is required")
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))


@dataclass(frozen=True)
class JTBDAnalysis:
    job_statement: str
    functional: str = ""
    emotional: str = ""
    social: str = ""

    def __post_init__(self) -> None:
        if not self.job_statement:
            raise ValueError("JTBDAnalysis.job_statement is required")


@dataclass(frozen=True)
class InterviewSummary:
    summary: str
    source: str
    interviewee: str = ""

    def __post_init__(self) -> None:
        if not self.summary:
            raise ValueError("InterviewSummary.summary is required")
        if not self.source:
            raise ValueError(
                "InterviewSummary.source is required - an interview summary is evidence, and evidence "
                "must state where it came from (ARR §7)"
            )


@dataclass(frozen=True)
class InterviewInsights:
    insights: tuple[str, ...]
    supporting_interview: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "insights", _as_tuple(self.insights))
        if not self.insights:
            raise ValueError("InterviewInsights.insights must not be empty")
        if not self.supporting_interview:
            raise ValueError("InterviewInsights.supporting_interview is required - insights must trace to an interview")


@dataclass(frozen=True)
class PersonaSummary:
    name: str
    segment: str = ""
    jobs: tuple[str, ...] = field(default_factory=tuple)
    pains: tuple[str, ...] = field(default_factory=tuple)
    goals: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("PersonaSummary.name is required")
        object.__setattr__(self, "jobs", _as_tuple(self.jobs))
        object.__setattr__(self, "pains", _as_tuple(self.pains))
        object.__setattr__(self, "goals", _as_tuple(self.goals))


@dataclass(frozen=True)
class HypothesisItem:
    statement: str
    status: HypothesisStatus = HypothesisStatus.UNKNOWN
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.statement:
            raise ValueError("HypothesisItem.statement is required")
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))


@dataclass(frozen=True)
class HypothesisList:
    items: tuple[HypothesisItem, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", _as_tuple(self.items))


@dataclass(frozen=True)
class OpportunityItem:
    title: str
    description: str = ""
    linked_job: str = ""
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("OpportunityItem.title is required")
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))


@dataclass(frozen=True)
class OpportunityList:
    items: tuple[OpportunityItem, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", _as_tuple(self.items))


@dataclass(frozen=True)
class DiscoveryRecommendation:
    recommendation: str
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_gap: str = ""

    def __post_init__(self) -> None:
        if not self.recommendation:
            raise ValueError("DiscoveryRecommendation.recommendation is required")
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        if not self.evidence_ids and not self.evidence_gap:
            raise ValueError(
                "DiscoveryRecommendation must cite supporting evidence_ids or state an explicit "
                "evidence_gap - a recommendation may never be silently ungrounded"
            )


@dataclass(frozen=True)
class DiscoverySummary:
    summary: str
    finding_count: int = 0
    open_questions: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.summary:
            raise ValueError("DiscoverySummary.summary is required")
        object.__setattr__(self, "open_questions", _as_tuple(self.open_questions))


@dataclass(frozen=True)
class DiscoveryReport:
    problem_statement: str
    hypotheses: tuple[str, ...] = field(default_factory=tuple)
    evidence_gaps: tuple[str, ...] = field(default_factory=tuple)
    opportunities: tuple[str, ...] = field(default_factory=tuple)
    recommendation: str = ""

    def __post_init__(self) -> None:
        if not self.problem_statement:
            raise ValueError("DiscoveryReport.problem_statement is required")
        object.__setattr__(self, "hypotheses", _as_tuple(self.hypotheses))
        object.__setattr__(self, "evidence_gaps", _as_tuple(self.evidence_gaps))
        object.__setattr__(self, "opportunities", _as_tuple(self.opportunities))
