"""LifeDomainState (P5 §3-§6): "what is currently happening in the
user's life" - current, relevant state per named LifeDomain, never a
running log of everything that has ever happened (§3's own explicit
"must NOT mean 'everything that has ever happened'").

This is a DIFFERENT concept from personal_state.py's own PersonalState:
PersonalState is a live, read-only VIEW assembled at request time from
CP-01/CP-02's own memory content (goals, projects, reflections...) via
AgentMemory - it owns nothing and persists nothing itself. LifeDomainState
is Personal-OS-owned structured state, in the same Application-owned
persistence category as DailyIntent/Pattern/Experiment - it is Personal
OS's own record of a domain's activation status and current focus,
independent of whatever CP-01/CP-02 happen to remember. The two are
complementary, never substitutable: a future integration could feed
PersonalState's memory content INTO a LifeDomainState update, but neither
module imports the other.

DEFAULT_CLASSIFICATION (§4) is the user's own explicit classification,
recorded as data, never as branching logic: CAREER/TECHNICAL_PROJECTS are
SEASONAL (can be activated and paused around real seasons of life);
BUSINESS/FINANCE_INVESTMENTS/PERSONAL_BRAND/LONG_TERM_GOALS are
PERSISTENT (ongoing concerns, rarely fully dormant); STUDY is persistent-
but-pausable (modeled as PERSISTENT here - persistence describes how the
domain behaves over time, not whether it happens to be paused right now,
which is what LifeDomainState.status is for); FAMILY is PERSISTENT
context, deliberately never a performance-tracked domain (§22 - this
module records no relationship/family "score" of any kind, only plain
context fields identical to every other domain's own shape);
EXPERIMENTS/COMMITMENTS are DYNAMIC - they exist only once something
concrete (an Experiment, a commitment) actually creates them."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.services.personal_os.shared.types import LifeDomain, LifeDomainClassification, LifeDomainStatus

DEFAULT_CLASSIFICATION: dict[LifeDomain, LifeDomainClassification] = {
    LifeDomain.CAREER: LifeDomainClassification.SEASONAL,
    LifeDomain.STUDY: LifeDomainClassification.PERSISTENT,
    LifeDomain.TECHNICAL_PROJECTS: LifeDomainClassification.SEASONAL,
    LifeDomain.BUSINESS: LifeDomainClassification.PERSISTENT,
    LifeDomain.FINANCE_INVESTMENTS: LifeDomainClassification.PERSISTENT,
    LifeDomain.PERSONAL_BRAND: LifeDomainClassification.PERSISTENT,
    LifeDomain.FAMILY: LifeDomainClassification.PERSISTENT,
    LifeDomain.LONG_TERM_GOALS: LifeDomainClassification.PERSISTENT,
    LifeDomain.EXPERIMENTS: LifeDomainClassification.DYNAMIC,
    LifeDomain.COMMITMENTS: LifeDomainClassification.DYNAMIC,
}


@dataclass(frozen=True)
class LifeDomainState:
    """One domain's current, relevant state (P5 §5) - deliberately a
    small, consolidated field set rather than one field per bullet point
    §5 lists: "associated goals" and "related missions" collapse into
    related_mission_ids (a Mission IS this model's goal-container
    concept - see mission.py - so a separate goals list would just
    duplicate it); "relevant context" and "recent developments" collapse
    into context_notes (both are free-text situational notes with no
    structural difference worth a second field); "active commitments"
    and "important deadlines" are represented by constraints/deadlines,
    kept as two fields because a constraint ("only weekends available")
    and a deadline ("visa renewal due March") are genuinely different
    kinds of fact, not because every noun in §5 needed its own slot."""

    domain: LifeDomain
    status: LifeDomainStatus
    classification: LifeDomainClassification
    objective: str = ""
    focus: str = ""
    context_notes: str = ""
    constraints: tuple[str, ...] = field(default_factory=tuple)
    deadlines: tuple[str, ...] = field(default_factory=tuple)
    related_mission_ids: tuple[str, ...] = field(default_factory=tuple)
    last_reviewed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    supersedes_state_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    state_id: str = ""

    def __post_init__(self) -> None:
        for name in ("constraints", "deadlines", "related_mission_ids"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))


def default_state(domain: LifeDomain) -> LifeDomainState:
    """A domain's honest starting point (§4) - NOT_STARTED, classified
    per DEFAULT_CLASSIFICATION, never fabricated as ACTIVE just because
    the domain exists in the enum. Every domain starts here until the
    user (or a future integration) actually reports something."""
    return LifeDomainState(domain=domain, status=LifeDomainStatus.NOT_STARTED, classification=DEFAULT_CLASSIFICATION[domain])
