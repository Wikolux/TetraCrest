"""CP-01 domain value objects: IdentityFact, Goal, GoalProgressUpdate,
Project, Reflection, Preference, PersonalIntelligenceRequest.

Covers: field defaults, validation (progress bounds), tuple coercion,
memory_type tagging, and to_memory_content() natural-language rendering -
the only "structured storage" this pack has, since the Memory model has
no metadata column (see shared/types.py's module docstring).
"""

import pytest

from app.services.ai.agents.specialists.personal_intelligence.shared.goal import (
    Goal,
    GoalCategory,
    GoalProgressUpdate,
    GoalStatus,
)
from app.services.ai.agents.specialists.personal_intelligence.shared.identity import IdentityAttribute, IdentityFact
from app.services.ai.agents.specialists.personal_intelligence.shared.preference import Preference
from app.services.ai.agents.specialists.personal_intelligence.shared.project import Project
from app.services.ai.agents.specialists.personal_intelligence.shared.reflection import Reflection, ReflectionPeriod
from app.services.ai.agents.specialists.personal_intelligence.shared.request import (
    PersonalIntelligenceOperation,
    PersonalIntelligenceRequest,
)
from app.services.ai.agents.specialists.personal_intelligence.shared.types import (
    ALL_MEMORY_TYPES,
    MEMORY_TYPE_GOAL,
    MEMORY_TYPE_IDENTITY,
    MEMORY_TYPE_PREFERENCE,
    MEMORY_TYPE_PROJECT,
    MEMORY_TYPE_REFLECTION,
)

# --- shared/types.py -------------------------------------------------------------------------


def test_every_memory_type_is_namespaced_with_personal_prefix():
    assert all(memory_type.startswith("personal_") for memory_type in ALL_MEMORY_TYPES)


def test_all_memory_types_contains_exactly_the_five_named_constants():
    assert set(ALL_MEMORY_TYPES) == {
        MEMORY_TYPE_IDENTITY,
        MEMORY_TYPE_GOAL,
        MEMORY_TYPE_PROJECT,
        MEMORY_TYPE_REFLECTION,
        MEMORY_TYPE_PREFERENCE,
    }


# --- IdentityFact ------------------------------------------------------------------------------


def test_identity_attribute_has_all_ten_documented_dimensions():
    assert {member.value for member in IdentityAttribute} == {
        "name",
        "preferred_name",
        "timezone",
        "language",
        "location",
        "occupation",
        "interests",
        "communication_style",
        "preferred_ai_personality",
        "preferred_response_style",
    }


def test_identity_fact_memory_type_is_personal_identity():
    assert IdentityFact(attribute=IdentityAttribute.NAME, value="Victor").memory_type == MEMORY_TYPE_IDENTITY


def test_identity_fact_title_humanizes_the_attribute():
    fact = IdentityFact(attribute=IdentityAttribute.COMMUNICATION_STYLE, value="direct")
    assert fact.title() == "Identity: communication style"


def test_identity_fact_to_memory_content_is_natural_language_prose():
    fact = IdentityFact(attribute=IdentityAttribute.TIMEZONE, value="America/Los_Angeles")
    assert fact.to_memory_content() == "The user's timezone is: America/Los_Angeles."


def test_identity_fact_is_frozen_and_hashable():
    fact = IdentityFact(attribute=IdentityAttribute.NAME, value="Victor")
    with pytest.raises(AttributeError):
        fact.value = "Someone else"
    hash(fact)  # must not raise


# --- Goal ---------------------------------------------------------------------------------------


def test_goal_defaults():
    goal = Goal(title="Ship CP-01")
    assert goal.description == ""
    assert goal.category == GoalCategory.PERSONAL
    assert goal.priority == 0
    assert goal.progress == 0.0
    assert goal.status == GoalStatus.ACTIVE
    assert goal.memory_type == MEMORY_TYPE_GOAL


@pytest.mark.parametrize("progress", [-1.0, 100.1, 1000.0])
def test_goal_rejects_out_of_bounds_progress(progress):
    with pytest.raises(ValueError, match="progress"):
        Goal(title="x", progress=progress)


@pytest.mark.parametrize("progress", [0.0, 50.0, 100.0])
def test_goal_accepts_boundary_progress(progress):
    assert Goal(title="x", progress=progress).progress == progress


def test_goal_to_memory_content_includes_title_category_status_priority_progress():
    goal = Goal(
        title="Ship CP-01",
        description="Deliver the personal intelligence pack",
        category=GoalCategory.CAREER,
        priority=1,
        progress=40.0,
        status=GoalStatus.ACTIVE,
    )
    content = goal.to_memory_content()
    assert "Ship CP-01" in content
    assert "career" in content
    assert "Deliver the personal intelligence pack" in content
    assert "active" in content
    assert "Priority: 1" in content
    assert "Progress: 40%" in content


def test_goal_to_memory_content_omits_description_when_blank():
    goal = Goal(title="x")
    assert "None" not in goal.to_memory_content()


def test_goal_status_has_four_documented_states():
    assert {member.value for member in GoalStatus} == {"active", "paused", "completed", "abandoned"}


def test_goal_category_has_six_documented_categories():
    assert {member.value for member in GoalCategory} == {
        "career",
        "learning",
        "business",
        "personal",
        "relationship",
        "financial",
    }


def test_goal_category_is_not_a_closed_vocabulary_at_runtime():
    # GoalCategory is deliberately a suggested, not enforced, vocabulary -
    # Goal.category is a plain str field, so an arbitrary string is legal.
    goal = Goal(title="x", category="side-project")
    assert goal.category == "side-project"
    assert "side-project" in goal.to_memory_content()


# --- GoalProgressUpdate --------------------------------------------------------------------------


def test_goal_progress_update_memory_type_is_personal_goal():
    update = GoalProgressUpdate(goal_title="Ship CP-01", note="Made good progress today")
    assert update.memory_type == MEMORY_TYPE_GOAL


def test_goal_progress_update_content_includes_note():
    update = GoalProgressUpdate(goal_title="Ship CP-01", note="Made good progress today")
    content = update.to_memory_content()
    assert "Ship CP-01" in content
    assert "Made good progress today" in content
    assert "Progress now" not in content
    assert "Status now" not in content


def test_goal_progress_update_content_includes_new_progress_when_given():
    update = GoalProgressUpdate(goal_title="x", note="note", new_progress=75.0)
    assert "Progress now 75%." in update.to_memory_content()


def test_goal_progress_update_content_includes_new_status_when_given():
    update = GoalProgressUpdate(goal_title="x", note="note", new_status=GoalStatus.COMPLETED)
    assert "Status now completed." in update.to_memory_content()


# --- Project ---------------------------------------------------------------------------------


def test_project_defaults():
    project = Project(name="AI Operating System")
    assert project.objective == ""
    assert project.milestones == ()
    assert project.progress == 0.0
    assert project.active is True
    assert project.memory_type == MEMORY_TYPE_PROJECT


def test_project_coerces_a_list_of_milestones_to_a_tuple():
    project = Project(name="x", milestones=["M13", "M20.7"])
    assert project.milestones == ("M13", "M20.7")
    assert isinstance(project.milestones, tuple)


@pytest.mark.parametrize("progress", [-0.01, 100.5])
def test_project_rejects_out_of_bounds_progress(progress):
    with pytest.raises(ValueError, match="progress"):
        Project(name="x", progress=progress)


def test_project_to_memory_content_includes_name_objective_milestones_active_progress():
    project = Project(
        name="AI Operating System",
        objective="Build a frozen AI OS architecture",
        milestones=("M13", "M20.7"),
        progress=80.0,
        active=True,
    )
    content = project.to_memory_content()
    assert "AI Operating System" in content
    assert "Build a frozen AI OS architecture" in content
    assert "M13; M20.7" in content
    assert "Active: True" in content
    assert "Progress: 80%" in content


def test_project_to_memory_content_omits_milestones_section_when_empty():
    project = Project(name="x")
    assert "Milestones" not in project.to_memory_content()


# --- Reflection --------------------------------------------------------------------------------


def test_reflection_defaults():
    reflection = Reflection(content="Today went well.")
    assert reflection.period == ReflectionPeriod.AD_HOC
    assert reflection.lessons == ()
    assert reflection.memory_type == MEMORY_TYPE_REFLECTION


def test_reflection_coerces_a_list_of_lessons_to_a_tuple():
    reflection = Reflection(content="x", lessons=["Ship smaller increments"])
    assert reflection.lessons == ("Ship smaller increments",)
    assert isinstance(reflection.lessons, tuple)


def test_reflection_period_has_three_documented_periods():
    assert {member.value for member in ReflectionPeriod} == {"daily", "weekly", "ad_hoc"}


def test_reflection_to_memory_content_includes_period_and_content():
    reflection = Reflection(content="Today went well.", period=ReflectionPeriod.DAILY)
    content = reflection.to_memory_content()
    assert "daily" in content
    assert "Today went well." in content


def test_reflection_to_memory_content_includes_lessons_when_given():
    reflection = Reflection(content="x", lessons=("Lesson one", "Lesson two"))
    content = reflection.to_memory_content()
    assert "Lessons learned: Lesson one; Lesson two." in content


def test_reflection_to_memory_content_omits_lessons_section_when_empty():
    reflection = Reflection(content="x")
    assert "Lessons" not in reflection.to_memory_content()


# --- Preference --------------------------------------------------------------------------------


def test_preference_defaults():
    preference = Preference(statement="I prefer concise answers.")
    assert preference.category == "general"
    assert preference.memory_type == MEMORY_TYPE_PREFERENCE


def test_preference_to_memory_content_includes_category_and_statement():
    preference = Preference(statement="Don't schedule meetings before 10am.", category="scheduling")
    content = preference.to_memory_content()
    assert "scheduling" in content
    assert "Don't schedule meetings before 10am." in content


# --- PersonalIntelligenceRequest -----------------------------------------------------------------


def test_personal_intelligence_operation_has_all_seven_documented_operations():
    assert {member.value for member in PersonalIntelligenceOperation} == {
        "remember_identity",
        "remember_goal",
        "update_goal_progress",
        "remember_project",
        "remember_reflection",
        "remember_preference",
        "recall",
    }


def test_personal_intelligence_request_defaults():
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.RECALL)
    assert request.text == ""
    assert request.title == ""
    assert request.category == ""
    assert request.priority == 0
    assert request.progress is None
    assert request.status == ""
    assert request.milestones == ()
    assert request.lessons == ()


def test_personal_intelligence_request_coerces_lists_to_tuples():
    request = PersonalIntelligenceRequest(
        operation=PersonalIntelligenceOperation.REMEMBER_PROJECT,
        milestones=["A", "B"],
        lessons=["C"],
    )
    assert request.milestones == ("A", "B")
    assert request.lessons == ("C",)


def test_personal_intelligence_request_is_frozen():
    request = PersonalIntelligenceRequest(operation=PersonalIntelligenceOperation.RECALL)
    with pytest.raises(AttributeError):
        request.text = "mutated"
