"""Morning Intelligence Brief (§8 of the build spec) - the internal
architecture and interfaces for all thirteen named domains, populated
this phase only where a real, already-existing data source exists
(CP-01/CP-02 memory, via PersonalState). Domains with no real integration
yet report an explicit "not yet connected" status rather than fabricated
content - per "do not fake external integrations," an empty, honestly
labeled section is correct; an invented one is not.

BriefSection is the one shape every domain renders through, so a future
domain (job opportunities, email intelligence, ...) is a new
BriefSectionProvider implementation, never a special case in
IntelligenceBrief itself - the same "one pattern, not one per channel"
discipline CP-02's Stakeholder Communication specialist already
established.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

from app.services.personal_os.daily_intent import DailyIntent
from app.services.personal_os.personal_state import PersonalState


class BriefSectionStatus(StrEnum):
    POPULATED = "populated"
    EMPTY = "empty"
    NOT_YET_CONNECTED = "not_yet_connected"


class BriefDomain(StrEnum):
    """The thirteen domains §8 names, in the order given there."""

    TODAY_PRIORITIES = "today_priorities"
    URGENT_DEADLINES = "urgent_deadlines"
    JOB_OPPORTUNITIES = "job_opportunities"
    MESSAGE_INTELLIGENCE = "message_intelligence"
    LEARNING_PRIORITIES = "learning_priorities"
    ACTIVE_PROJECTS = "active_projects"
    UNFINISHED_COMMITMENTS = "unfinished_commitments"
    BUSINESS_OPPORTUNITIES = "business_opportunities"
    FINANCIAL_INTELLIGENCE = "financial_intelligence"
    WORLD_AFFAIRS = "world_affairs"
    CONTENT_PERFORMANCE = "content_performance"
    GROWTH_OBSERVATIONS = "growth_observations"
    MOTIVATION_CONTEXT = "motivation_context"


@dataclass(frozen=True)
class BriefSection:
    domain: BriefDomain
    status: BriefSectionStatus
    items: tuple[str, ...] = field(default_factory=tuple)
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple):
            object.__setattr__(self, "items", tuple(self.items))
        if self.status == BriefSectionStatus.POPULATED and not self.items:
            raise ValueError("BriefSection.status=POPULATED requires at least one item")


@dataclass(frozen=True)
class IntelligenceBrief:
    intent: DailyIntent
    sections: tuple[BriefSection, ...]

    def section_for(self, domain: BriefDomain) -> BriefSection | None:
        return next((section for section in self.sections if section.domain == domain), None)


class BriefSectionProvider(ABC):
    """One domain's own way of producing its BriefSection. A provider
    with no real data source returns NOT_YET_CONNECTED rather than being
    omitted, so the brief's own shape (thirteen domains) is stable even
    before every domain has a real integration."""

    domain: BriefDomain

    @abstractmethod
    def provide(self, state: PersonalState, intent: DailyIntent) -> BriefSection:
        raise NotImplementedError


class _NotYetConnectedProvider(BriefSectionProvider):
    """The honest default for every domain this phase does not yet have
    a real data source for - used directly, never subclassed per domain,
    since "not yet connected" needs no domain-specific logic."""

    def __init__(self, domain: BriefDomain) -> None:
        self.domain = domain

    def provide(self, state: PersonalState, intent: DailyIntent) -> BriefSection:
        return BriefSection(
            domain=self.domain,
            status=BriefSectionStatus.NOT_YET_CONNECTED,
            note=f"{self.domain.value} has no connected data source yet - deferred to a future milestone.",
        )


class TodayPrioritiesProvider(BriefSectionProvider):
    domain = BriefDomain.TODAY_PRIORITIES

    def provide(self, state: PersonalState, intent: DailyIntent) -> BriefSection:
        items = tuple(activity.description for activity in intent.planned_activities)
        if not items:
            return BriefSection(domain=self.domain, status=BriefSectionStatus.EMPTY, note="No activities planned yet today.")
        return BriefSection(domain=self.domain, status=BriefSectionStatus.POPULATED, items=items)


class UnfinishedCommitmentsProvider(BriefSectionProvider):
    domain = BriefDomain.UNFINISHED_COMMITMENTS

    def provide(self, state: PersonalState, intent: DailyIntent) -> BriefSection:
        items = tuple(item.content for item in (*state.goals, *state.projects))
        if not items:
            return BriefSection(domain=self.domain, status=BriefSectionStatus.EMPTY, note="No open goals or projects on record.")
        return BriefSection(domain=self.domain, status=BriefSectionStatus.POPULATED, items=items)


class ActiveProjectsProvider(BriefSectionProvider):
    domain = BriefDomain.ACTIVE_PROJECTS

    def provide(self, state: PersonalState, intent: DailyIntent) -> BriefSection:
        items = tuple(item.content for item in state.projects)
        if not items:
            return BriefSection(domain=self.domain, status=BriefSectionStatus.EMPTY, note="No active projects on record.")
        return BriefSection(domain=self.domain, status=BriefSectionStatus.POPULATED, items=items)


# The four domains with a real, already-wired CP-01/CP-02 data source
# this phase (TodayPrioritiesProvider draws on DailyIntent itself, not
# PersonalState). Every other domain is honestly NOT_YET_CONNECTED.
_DEFAULT_PROVIDERS: tuple[BriefSectionProvider, ...] = (
    TodayPrioritiesProvider(),
    UnfinishedCommitmentsProvider(),
    ActiveProjectsProvider(),
    *(
        _NotYetConnectedProvider(domain)
        for domain in BriefDomain
        if domain
        not in (BriefDomain.TODAY_PRIORITIES, BriefDomain.UNFINISHED_COMMITMENTS, BriefDomain.ACTIVE_PROJECTS)
    ),
)


class IntelligenceBriefBuilder:
    def __init__(self, providers: tuple[BriefSectionProvider, ...] = _DEFAULT_PROVIDERS) -> None:
        self.providers = providers

    def build(self, state: PersonalState, intent: DailyIntent) -> IntelligenceBrief:
        sections = tuple(provider.provide(state, intent) for provider in self.providers)
        return IntelligenceBrief(intent=intent, sections=sections)
