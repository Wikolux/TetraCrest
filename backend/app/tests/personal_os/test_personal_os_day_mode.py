"""DayMode (P5 §11-§12): asking before planning, structured/flexible/
recovery/family/project/study modes, custom user-defined modes, and how
day mode influences (never permanently changes) ranking-relevant tables."""

import pytest

from app.services.personal_os.day_mode import DAY_MODE_DOMAIN_BOOST, DAY_MODE_REDUCES_OPTIONAL, DAY_MODE_SUPPRESSES_WORK, DayMode, infer_day_mode
from app.services.personal_os.shared.types import DayModeKind, LifeDomain


def test_custom_day_mode_requires_a_label():
    with pytest.raises(ValueError):
        DayMode(kind=DayModeKind.CUSTOM)


def test_named_day_mode_rejects_a_custom_label():
    with pytest.raises(ValueError):
        DayMode(kind=DayModeKind.STRUCTURED_PRODUCTIVE, custom_label="deep work")


def test_custom_day_mode_preserves_the_users_own_words():
    mode = DayMode(kind=DayModeKind.CUSTOM, custom_label="Slow creative morning")
    assert mode.label == "Slow creative morning"


def test_named_day_mode_label_is_readable():
    mode = DayMode(kind=DayModeKind.FAMILY_FOCUSED)
    assert mode.label == "family focused"


# --- infer_day_mode: structured, flexible, recovery, family, project, study, custom --------------


def test_infers_structured_productive():
    assert infer_day_mode("I want a focused workday").kind == DayModeKind.STRUCTURED_PRODUCTIVE


def test_infers_flexible():
    assert infer_day_mode("Let's play it by ear today").kind == DayModeKind.FLEXIBLE


def test_infers_recovery():
    assert infer_day_mode("I need a recovery day, taking it easy").kind == DayModeKind.RECOVERY


def test_infers_family_focused():
    assert infer_day_mode("Family day today, with the kids").kind == DayModeKind.FAMILY_FOCUSED


def test_infers_project_focused():
    assert infer_day_mode("It's a project day, shipping day").kind == DayModeKind.PROJECT_FOCUSED


def test_infers_study_focused():
    assert infer_day_mode("Today is a study day").kind == DayModeKind.STUDY_FOCUSED


def test_no_match_returns_none_honestly():
    assert infer_day_mode("xyzzy the frobnicator") is None


def test_empty_text_returns_none():
    assert infer_day_mode("") is None


# --- day mode influences ranking tables, never permanently (§12) ---------------------------------


def test_project_focused_boosts_project_and_business_domains():
    assert LifeDomain.TECHNICAL_PROJECTS in DAY_MODE_DOMAIN_BOOST[DayModeKind.PROJECT_FOCUSED]
    assert LifeDomain.BUSINESS in DAY_MODE_DOMAIN_BOOST[DayModeKind.PROJECT_FOCUSED]


def test_study_focused_boosts_study_domain():
    assert DAY_MODE_DOMAIN_BOOST[DayModeKind.STUDY_FOCUSED] == (LifeDomain.STUDY,)


def test_family_focused_and_recovery_suppress_work():
    assert DayModeKind.FAMILY_FOCUSED in DAY_MODE_SUPPRESSES_WORK
    assert DayModeKind.RECOVERY in DAY_MODE_SUPPRESSES_WORK
    assert DayModeKind.STRUCTURED_PRODUCTIVE not in DAY_MODE_SUPPRESSES_WORK


def test_recovery_and_family_focused_reduce_optional_workload():
    assert DayModeKind.RECOVERY in DAY_MODE_REDUCES_OPTIONAL
    assert DayModeKind.FAMILY_FOCUSED in DAY_MODE_REDUCES_OPTIONAL
    assert DayModeKind.STRUCTURED_PRODUCTIVE not in DAY_MODE_REDUCES_OPTIONAL
