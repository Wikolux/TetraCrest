"""IntelligenceBriefBuilder (§8): all thirteen domains present, each
honestly labeled populated/empty/not-yet-connected - never fabricated."""

from datetime import date

from app.services.personal_os.brief import BriefDomain, BriefSectionStatus, IntelligenceBriefBuilder
from app.services.personal_os.daily_intent import DailyIntent, PlannedActivity
from app.services.personal_os.personal_state import PersonalState, PersonalStateItem
from app.services.personal_os.shared.types import DayType


def _intent(activities=()):
    return DailyIntent(intent_date=date(2026, 8, 13), stated_intention="x", day_type=DayType.WORK, planned_activities=activities)


def test_brief_contains_all_thirteen_named_domains():
    brief = IntelligenceBriefBuilder().build(PersonalState(), _intent())
    domains_present = {section.domain for section in brief.sections}
    assert domains_present == set(BriefDomain)


def test_today_priorities_populated_from_planned_activities():
    intent = _intent(activities=(PlannedActivity(description="Draft the PRD"),))
    brief = IntelligenceBriefBuilder().build(PersonalState(), intent)
    section = brief.section_for(BriefDomain.TODAY_PRIORITIES)
    assert section.status == BriefSectionStatus.POPULATED
    assert "Draft the PRD" in section.items


def test_domains_with_no_data_source_are_honestly_not_yet_connected():
    """Job opportunities, email intelligence, world affairs, etc. have no
    real integration this phase - never fabricated content."""
    brief = IntelligenceBriefBuilder().build(PersonalState(), _intent())
    for domain in (BriefDomain.JOB_OPPORTUNITIES, BriefDomain.MESSAGE_INTELLIGENCE, BriefDomain.WORLD_AFFAIRS, BriefDomain.FINANCIAL_INTELLIGENCE):
        section = brief.section_for(domain)
        assert section.status == BriefSectionStatus.NOT_YET_CONNECTED
        assert section.items == ()


def test_unfinished_commitments_reads_from_personal_state_goals_and_projects():
    from datetime import UTC, datetime

    state = PersonalState(goals=(PersonalStateItem(memory_type="personal_goal", content="Ship v2", resource_id=1, created_at=datetime.now(UTC)),))
    brief = IntelligenceBriefBuilder().build(state, _intent())
    section = brief.section_for(BriefDomain.UNFINISHED_COMMITMENTS)
    assert section.status == BriefSectionStatus.POPULATED
    assert "Ship v2" in section.items


def test_empty_state_produces_empty_not_populated_sections_for_real_providers():
    brief = IntelligenceBriefBuilder().build(PersonalState(), _intent())
    section = brief.section_for(BriefDomain.UNFINISHED_COMMITMENTS)
    assert section.status == BriefSectionStatus.EMPTY
