"""InsightEngine - the deterministic core: pattern/habit/contradiction/
alignment detection, recommendation/periodic-reflection/profile
synthesis. Pure, no I/O - every test here constructs ContextItems by
hand and asserts on exact, reproducible output, mirroring
ResearchSynthesizer's own "pure function" test discipline.

The properties under test throughout: (1) every produced Insight's
supporting_memory_ids traces back to the exact input items that produced
it - never invented, never omitted; (2) OBSERVED insights state a plain
fact; INFERRED insights always carry a conclusion built from that fact;
(3) the engine never raises on an empty corpus - "no signal" is a valid,
low-confidence answer, not an error.
"""

from datetime import UTC, datetime

from app.services.ai.agents.specialists.personal_intelligence.insight.engine import InsightEngine
from app.services.ai.agents.specialists.personal_intelligence.shared.insight import InsightBasis, InsightPeriod, InsightType
from app.services.context.types import ContextItem


def _item(resource_id: int, content: str, memory_type: str = "personal_reflection", title: str = "") -> ContextItem:
    return ContextItem(
        resource_type="memory",
        resource_id=resource_id,
        content=content,
        score=1.0,
        created_at=datetime.now(UTC),
        metadata={"memory_type": memory_type, "title": title},
    )


# --- detect_patterns -----------------------------------------------------------------------


def test_detect_patterns_finds_a_term_recurring_at_or_above_the_threshold():
    items = (
        _item(1, "Consistency has been difficult this week."),
        _item(2, "I struggled with consistency again today."),
        _item(3, "Overall a good week, consistency improved slightly."),
    )
    insights = InsightEngine().detect_patterns(items, minimum_occurrences=3)
    assert len(insights) == 1
    assert insights[0].subject == "consistency"
    assert insights[0].insight_type == InsightType.PATTERN
    assert insights[0].basis == InsightBasis.OBSERVED


def test_detect_patterns_excludes_a_term_below_the_threshold():
    items = (_item(1, "Consistency has been difficult."), _item(2, "Something else entirely unrelated here."))
    insights = InsightEngine().detect_patterns(items, minimum_occurrences=3)
    assert insights == ()


def test_detect_patterns_supporting_memory_ids_are_exactly_the_matching_items():
    items = (
        _item(1, "Consistency issue."),
        _item(2, "Consistency issue again."),
        _item(3, "Consistency issue a third time."),
        _item(4, "Totally unrelated content here."),
    )
    insights = InsightEngine().detect_patterns(items, minimum_occurrences=3)
    assert insights[0].supporting_memory_ids == (1, 2, 3)


def test_detect_patterns_observation_states_the_raw_count():
    items = tuple(_item(i, "recurring term appears here") for i in range(1, 4))
    insights = InsightEngine().detect_patterns(items, minimum_occurrences=3)
    assert "3 separate memories" in insights[0].observation


def test_detect_patterns_on_an_empty_corpus_returns_nothing_and_does_not_raise():
    assert InsightEngine().detect_patterns((), minimum_occurrences=3) == ()


def test_detect_patterns_ignores_cp01_template_boilerplate_words():
    # "Goal"/"Status"/"Priority"/"Reflection"/"daily" etc. appear in every
    # rendering of their type - these must never surface as a "pattern".
    items = (
        _item(1, "Reflection (daily): first entry."),
        _item(2, "Reflection (daily): second entry."),
        _item(3, "Reflection (daily): third entry."),
    )
    insights = InsightEngine().detect_patterns(items, minimum_occurrences=3)
    subjects = {insight.subject for insight in insights}
    assert "reflection" not in subjects
    assert "daily" not in subjects


def test_detect_patterns_confidence_increases_with_more_occurrences():
    at_threshold = InsightEngine().detect_patterns(
        tuple(_item(i, "signal word here") for i in range(1, 4)), minimum_occurrences=3
    )[0]
    above_threshold = InsightEngine().detect_patterns(
        tuple(_item(i, "signal word here") for i in range(1, 8)), minimum_occurrences=3
    )[0]
    assert above_threshold.confidence > at_threshold.confidence


def test_detect_patterns_confidence_never_exceeds_one():
    items = tuple(_item(i, "signal word here") for i in range(1, 50))
    insights = InsightEngine().detect_patterns(items, minimum_occurrences=3)
    assert all(insight.confidence <= 1.0 for insight in insights)


def test_detect_patterns_is_deterministic():
    items = (_item(1, "alpha beta"), _item(2, "alpha gamma"), _item(3, "alpha delta"))
    engine = InsightEngine()
    first = engine.detect_patterns(items, minimum_occurrences=3)
    second = engine.detect_patterns(items, minimum_occurrences=3)
    assert first == second


def test_detect_patterns_short_words_are_excluded():
    items = tuple(_item(i, "a an it is") for i in range(1, 5))
    assert InsightEngine().detect_patterns(items, minimum_occurrences=3) == ()


# --- identify_habits -------------------------------------------------------------------------


def test_identify_habits_reuses_pattern_detection_but_labels_as_inferred_habit():
    items = tuple(_item(i, "procrastination shows up again") for i in range(1, 4))
    insights = InsightEngine().identify_habits(items, minimum_occurrences=2)
    assert len(insights) >= 1
    habit = next(i for i in insights if i.subject == "procrastination")
    assert habit.insight_type == InsightType.HABIT
    assert habit.basis == InsightBasis.INFERRED
    assert "habit" in habit.conclusion.lower() or "trend" in habit.conclusion.lower()


def test_identify_habits_preserves_the_same_supporting_memory_ids_as_the_underlying_pattern():
    items = (_item(1, "procrastination again"), _item(2, "procrastination once more"))
    patterns = InsightEngine().detect_patterns(items, minimum_occurrences=2)
    habits = InsightEngine().identify_habits(items, minimum_occurrences=2)
    assert habits[0].supporting_memory_ids == patterns[0].supporting_memory_ids


def test_identify_habits_on_empty_reflections_returns_nothing():
    assert InsightEngine().identify_habits((), minimum_occurrences=2) == ()


# --- detect_contradictions --------------------------------------------------------------------


def test_detect_contradictions_flags_a_negated_preference_term_appearing_unnegated_elsewhere():
    preferences = (_item(1, "Don't schedule meetings before 10am.", memory_type="personal_preference"),)
    comparisons = (_item(2, "Scheduled a meetings slot at 8am today.", memory_type="personal_goal"),)
    insights = InsightEngine().detect_contradictions(preferences, comparisons)
    assert len(insights) == 1
    assert insights[0].subject == "meetings"
    assert insights[0].insight_type == InsightType.CONTRADICTION
    assert insights[0].basis == InsightBasis.INFERRED
    assert set(insights[0].supporting_memory_ids) == {1, 2}


def test_detect_contradictions_confidence_is_deliberately_modest():
    preferences = (_item(1, "Don't schedule meetings before 10am.", memory_type="personal_preference"),)
    comparisons = (_item(2, "Scheduled a meetings slot at 8am today.", memory_type="personal_goal"),)
    insight = InsightEngine().detect_contradictions(preferences, comparisons)[0]
    assert insight.confidence < 0.5


def test_detect_contradictions_does_not_flag_when_the_candidate_also_negates_the_term():
    preferences = (_item(1, "Don't schedule meetings before 10am.", memory_type="personal_preference"),)
    comparisons = (_item(2, "I will not schedule any meetings early either.", memory_type="personal_goal"),)
    assert InsightEngine().detect_contradictions(preferences, comparisons) == ()


def test_detect_contradictions_returns_nothing_when_no_preferences_negate_anything():
    preferences = (_item(1, "I love mornings and meetings.", memory_type="personal_preference"),)
    comparisons = (_item(2, "Had a meetings slot at 8am.", memory_type="personal_goal"),)
    assert InsightEngine().detect_contradictions(preferences, comparisons) == ()


def test_detect_contradictions_on_empty_inputs_returns_nothing():
    assert InsightEngine().detect_contradictions((), ()) == ()


def test_detect_contradictions_is_deterministic():
    preferences = (_item(1, "Don't schedule meetings before 10am.", memory_type="personal_preference"),)
    comparisons = (_item(2, "Scheduled a meetings slot at 8am today.", memory_type="personal_goal"),)
    engine = InsightEngine()
    first = engine.detect_contradictions(preferences, comparisons)
    second = engine.detect_contradictions(preferences, comparisons)
    assert first == second


# --- measure_alignment -----------------------------------------------------------------------


def test_measure_alignment_scores_a_goal_referenced_in_recent_activity_as_well_aligned():
    goals = (_item(1, "Goal (career): AI Operating System.", memory_type="personal_goal", title="AI Operating System"),)
    recent = tuple(_item(i, "Worked on the AI Operating System today.", memory_type="personal_reflection") for i in range(2, 6))
    insights = InsightEngine().measure_alignment(goals, recent)
    assert len(insights) == 1
    assert "well-aligned" in insights[0].conclusion
    assert insights[0].subject == "AI Operating System"


def test_measure_alignment_scores_a_goal_never_mentioned_as_not_appearing():
    goals = (_item(1, "Goal (career): Learn Mandarin.", memory_type="personal_goal", title="Learn Mandarin"),)
    recent = (_item(2, "Worked on the website redesign today.", memory_type="personal_reflection"),)
    insights = InsightEngine().measure_alignment(goals, recent)
    assert "not appearing" in insights[0].conclusion


def test_measure_alignment_with_no_recent_activity_does_not_raise():
    goals = (_item(1, "Goal (career): Learn Mandarin.", memory_type="personal_goal", title="Learn Mandarin"),)
    insights = InsightEngine().measure_alignment(goals, ())
    assert insights[0].confidence < 0.6
    assert "not appearing" in insights[0].conclusion


def test_measure_alignment_supporting_ids_include_the_goal_and_matching_activity():
    goals = (_item(1, "Goal (career): AI Operating System.", memory_type="personal_goal", title="AI Operating System"),)
    recent = (_item(2, "Worked on the AI Operating System today.", memory_type="personal_reflection"),)
    insight = InsightEngine().measure_alignment(goals, recent)[0]
    assert set(insight.supporting_memory_ids) == {1, 2}


def test_measure_alignment_on_no_goals_returns_nothing():
    assert InsightEngine().measure_alignment((), (_item(1, "x"),)) == ()


# --- generate_recommendations ------------------------------------------------------------------


def test_generate_recommendations_from_contradictions():
    contradiction = InsightEngine().detect_contradictions(
        (_item(1, "Don't schedule meetings before 10am.", memory_type="personal_preference"),),
        (_item(2, "Scheduled a meetings slot at 8am today.", memory_type="personal_goal"),),
    )
    recs = InsightEngine().generate_recommendations(contradiction_insights=contradiction)
    assert len(recs) == 1
    assert recs[0].insight_type == InsightType.RECOMMENDATION
    assert recs[0].supporting_memory_ids == contradiction[0].supporting_memory_ids


def test_generate_recommendations_from_low_alignment_goals():
    alignment = InsightEngine().measure_alignment(
        (_item(1, "Goal (career): Learn Mandarin.", memory_type="personal_goal", title="Learn Mandarin"),),
        (_item(2, "Worked on something unrelated.", memory_type="personal_reflection"),),
    )
    recs = InsightEngine().generate_recommendations(alignment_insights=alignment)
    assert len(recs) == 1
    assert "Learn Mandarin" in recs[0].title


def test_generate_recommendations_skips_well_aligned_goals():
    alignment = InsightEngine().measure_alignment(
        (_item(1, "Goal (career): AI Operating System.", memory_type="personal_goal", title="AI Operating System"),),
        tuple(_item(i, "Worked on the AI Operating System today.", memory_type="personal_reflection") for i in range(2, 6)),
    )
    recs = InsightEngine().generate_recommendations(alignment_insights=alignment)
    assert recs == ()


def test_generate_recommendations_from_habits():
    habits = InsightEngine().identify_habits(
        tuple(_item(i, "procrastination shows up") for i in range(1, 4)), minimum_occurrences=2
    )
    recs = InsightEngine().generate_recommendations(habit_insights=habits)
    assert len(recs) == len(habits)


def test_generate_recommendations_with_no_inputs_returns_nothing():
    assert InsightEngine().generate_recommendations() == ()


# --- generate_periodic_reflection ---------------------------------------------------------------


def test_generate_periodic_reflection_names_the_period_in_the_title():
    reflection = InsightEngine().generate_periodic_reflection(period=InsightPeriod.WEEKLY, window_items=())
    assert reflection.title == "Weekly reflection"
    assert reflection.insight_type == InsightType.PERIODIC_REFLECTION


def test_generate_periodic_reflection_over_an_empty_window_has_zero_confidence_and_no_supporting_ids():
    reflection = InsightEngine().generate_periodic_reflection(period=InsightPeriod.DAILY, window_items=())
    assert reflection.confidence == 0.0
    assert reflection.supporting_memory_ids == ()
    assert "0 memories" in reflection.observation


def test_generate_periodic_reflection_supporting_ids_include_window_items_and_insight_evidence():
    window = (_item(1, "consistency again"), _item(2, "consistency once more"), _item(3, "consistency a third time"))
    patterns = InsightEngine().detect_patterns(window, minimum_occurrences=3)
    reflection = InsightEngine().generate_periodic_reflection(
        period=InsightPeriod.WEEKLY, window_items=window, pattern_insights=patterns
    )
    assert {1, 2, 3}.issubset(set(reflection.supporting_memory_ids))


def test_generate_periodic_reflection_highlights_recurring_pattern_subjects():
    window = tuple(_item(i, "consistency shows up") for i in range(1, 4))
    patterns = InsightEngine().detect_patterns(window, minimum_occurrences=3)
    reflection = InsightEngine().generate_periodic_reflection(
        period=InsightPeriod.WEEKLY, window_items=window, pattern_insights=patterns
    )
    assert "consistency" in reflection.conclusion


# --- synthesize_profile -----------------------------------------------------------------------


def test_synthesize_profile_with_no_insights_is_honest_about_having_nothing():
    profile = InsightEngine().synthesize_profile(recent_insights=())
    assert profile.insight_type == InsightType.PROFILE_SUMMARY
    assert "Not enough data" in profile.conclusion
    assert profile.supporting_memory_ids == ()


def test_synthesize_profile_aggregates_supporting_ids_from_every_input_insight():
    patterns = InsightEngine().detect_patterns(
        tuple(_item(i, "consistency shows up") for i in range(1, 4)), minimum_occurrences=3
    )
    profile = InsightEngine().synthesize_profile(recent_insights=patterns)
    assert set(profile.supporting_memory_ids) == {1, 2, 3}


def test_synthesize_profile_confidence_grows_with_more_input_insights():
    patterns = InsightEngine().detect_patterns(
        tuple(_item(i, f"term{i % 3} recurs") for i in range(1, 12)), minimum_occurrences=3
    )
    few = InsightEngine().synthesize_profile(recent_insights=patterns[:1])
    many = InsightEngine().synthesize_profile(recent_insights=patterns)
    assert many.confidence >= few.confidence


def test_synthesize_profile_is_deterministic():
    patterns = InsightEngine().detect_patterns(
        tuple(_item(i, "consistency shows up") for i in range(1, 4)), minimum_occurrences=3
    )
    engine = InsightEngine()
    first = engine.synthesize_profile(recent_insights=patterns)
    second = engine.synthesize_profile(recent_insights=patterns)
    assert first == second
