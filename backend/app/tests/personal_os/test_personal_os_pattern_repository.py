"""PatternRepository (P3 §10, §14): the in-memory reference
implementation's own append-only, status-tracked lifecycle - the same
contract SqlPatternRepository (tested separately, against a real
database, in test_personal_os_sql_repository.py) must also satisfy."""

from datetime import date

from app.services.personal_os.pattern import Pattern, PatternEvidenceItem
from app.services.personal_os.pattern_repository import InMemoryPatternRepository
from app.services.personal_os.reasoning import ObservedFact
from app.services.personal_os.shared.types import Confidence, PatternStatus, PatternType

ORG_ID, USER_ID = 1, 2


def _pattern(pattern_id="", status=PatternStatus.OBSERVED, pattern_type=PatternType.REPEATED_POSTPONEMENT):
    facts = (ObservedFact(statement="fact one"), ObservedFact(statement="fact two"))
    evidence = (
        PatternEvidenceItem(observation_date=date(2026, 7, 1), activity_description="x", activity_category="learning", status="postponed"),
        PatternEvidenceItem(observation_date=date(2026, 7, 3), activity_description="x", activity_category="learning", status="postponed"),
    )
    return Pattern(
        pattern_id=pattern_id,
        pattern_type=pattern_type,
        observation_window_start=date(2026, 7, 1),
        observation_window_end=date(2026, 7, 3),
        evidence=evidence,
        observed_facts=facts,
        pattern_statement="2 activities postponed",
        confidence=Confidence.LOW,
        status=status,
    )


def test_save_assigns_a_pattern_id_when_none_is_given():
    repo = InMemoryPatternRepository()
    saved = repo.save(_pattern(), organization_id=ORG_ID, user_id=USER_ID)
    assert saved.pattern_id != ""


def test_get_latest_returns_none_when_nothing_saved():
    repo = InMemoryPatternRepository()
    assert repo.get_latest(organization_id=ORG_ID, user_id=USER_ID, pattern_type=PatternType.REPEATED_POSTPONEMENT) is None


def test_get_latest_returns_the_most_recently_saved_version():
    repo = InMemoryPatternRepository()
    first = repo.save(_pattern(status=PatternStatus.OBSERVED), organization_id=ORG_ID, user_id=USER_ID)
    from dataclasses import replace

    repo.save(replace(first, status=PatternStatus.CONFIRMED), organization_id=ORG_ID, user_id=USER_ID)

    latest = repo.get_latest(organization_id=ORG_ID, user_id=USER_ID, pattern_type=PatternType.REPEATED_POSTPONEMENT)
    assert latest.status == PatternStatus.CONFIRMED


def test_list_active_excludes_dismissed_and_superseded():
    repo = InMemoryPatternRepository()
    repo.save(_pattern(pattern_type=PatternType.REPEATED_POSTPONEMENT, status=PatternStatus.CONFIRMED), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_pattern(pattern_type=PatternType.ESTIMATION_ACCURACY, status=PatternStatus.DISMISSED), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_pattern(pattern_type=PatternType.RECURRING_BLOCKER, status=PatternStatus.SUPERSEDED), organization_id=ORG_ID, user_id=USER_ID)

    active = repo.list_active(organization_id=ORG_ID, user_id=USER_ID)
    assert len(active) == 1
    assert active[0].pattern_type == PatternType.REPEATED_POSTPONEMENT


def test_list_active_scopes_by_organization_and_user():
    repo = InMemoryPatternRepository()
    repo.save(_pattern(status=PatternStatus.OBSERVED), organization_id=ORG_ID, user_id=USER_ID)
    repo.save(_pattern(status=PatternStatus.OBSERVED), organization_id=ORG_ID, user_id=99)

    active = repo.list_active(organization_id=ORG_ID, user_id=USER_ID)
    assert len(active) == 1
