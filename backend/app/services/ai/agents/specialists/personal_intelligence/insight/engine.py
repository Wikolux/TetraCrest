"""InsightEngine - the deterministic core of Executive Cognition: turns a
corpus of already-retrieved ContextItems into Insight objects.

Pure by design, mirroring ResearchSynthesizer's own precedent exactly
(app.services.ai.agents.specialists.research.synthesizer - "no I/O, same
input always produces the same output"). This is deliberate, not merely
convenient: "every generated insight must be traceable back to supporting
memories rather than invented" is only guaranteed if the detection logic
itself is mechanical and reproducible - a rule-based term-frequency/
negation-window heuristic can never hallucinate a memory that wasn't
there, the way an LLM-driven "find patterns in this text" call could.
AIRuntime is deliberately NOT used anywhere in this module; InsightAgent
reserves the Runtime for one thing only - rendering a natural-language
answer to an explicit RECALL_INSIGHTS query - exactly mirroring how
PersonalIntelligenceAgent only calls the Runtime for its own RECALL
operation, never for a remember_*() write.

Every heuristic here is intentionally simple and bounded, not full NLU:

- Pattern/habit detection: a normalized term recurring across >= N
  distinct memories is "observed" (a plain count); habits are the same
  mechanism scoped to Reflection-type memories and labeled as a
  behavioral signal rather than a topical one.
- Contradiction detection: a Preference containing a negation marker
  ("don't", "not", "avoid", ...) followed by a term, matched against a
  Goal/Project/Reflection that contains the same term without a nearby
  negation. Coarse by design - confidence is set low (0.4) to reflect
  that.
- Alignment: the fraction of "recent activity" memories that share
  vocabulary with a given goal's own content - a goal that never recurs
  in recent activity scores near zero ("not appearing"), independent of
  how important the user considers it.

None of this is adaptive or self-tuning - identical to ExecutivePlanner/
ResearchPlanner's own "deterministic, rule-based, never by analyzing the
meaning of the request text itself" philosophy, just applied to insight
detection instead of task planning.
"""

import re
from collections import Counter, defaultdict

from app.services.ai.agents.specialists.personal_intelligence.shared.insight import (
    Insight,
    InsightBasis,
    InsightPeriod,
    InsightType,
)
from app.services.context.types import ContextItem

__all__ = ["InsightEngine"]

_WORD_PATTERN = re.compile(r"[a-z0-9]+")

# Generic English stopwords plus CP-01's own template/structural
# vocabulary (words that appear in every to_memory_content() rendering
# regardless of subject matter - e.g. "Status: active. Priority: 1." -
# and would otherwise trivially "recur" across every single memory,
# drowning out genuine signal).
_STOPWORDS = frozenset(
    {
        "the", "and", "or", "is", "are", "was", "were", "to", "of", "in", "on", "for", "with", "that", "this",
        "my", "your", "you", "it", "be", "been", "being", "have", "has", "had", "not", "but", "at", "as", "by",
        "from", "will", "would", "should", "could", "can", "does", "did", "so", "if", "then", "than", "just",
        "about", "into", "over", "up", "down", "out", "who", "what", "when", "where", "why", "how", "all",
        "any", "both", "each", "few", "more", "most", "other", "some", "such", "only", "own", "same", "too",
        "very", "user", "users", "status", "priority", "progress", "active", "objective", "milestones",
        "lessons", "learned", "supporting", "memories", "observed", "inferred", "insight", "insights", "true",
        "false", "update", "updates", "recorded",
        # CP-01's own per-type template words - every Goal/Project/Reflection/
        # Preference/Identity rendering repeats its own type name and (for
        # Reflection) its period, which would otherwise "recur" trivially
        # across every memory of that type regardless of actual content.
        "goal", "goals", "project", "projects", "reflection", "reflections", "preference", "preferences",
        "identity", "daily", "weekly", "monthly",
    }
)

# Negation markers - apostrophes are stripped before tokenizing, so
# "don't"/"can't"/"won't" normalize to "dont"/"cant"/"wont".
_NEGATION_MARKERS = frozenset(
    {"dont", "not", "avoid", "no", "never", "cant", "cannot", "wont", "isnt", "arent", "doesnt", "didnt"}
)
_NEGATION_WINDOW = 5

_DEFAULT_MINIMUM_WORD_LENGTH = 4
_DEFAULT_PATTERN_MINIMUM_OCCURRENCES = 3
_DEFAULT_HABIT_MINIMUM_OCCURRENCES = 2
_ALIGNMENT_WELL_ALIGNED_THRESHOLD = 0.3
_CONTRADICTION_CONFIDENCE = 0.4


def _ordered_terms(content: str) -> list[str]:
    normalized = content.lower().replace("'", "")
    return _WORD_PATTERN.findall(normalized)


def _distinct_terms(content: str, minimum_word_length: int = _DEFAULT_MINIMUM_WORD_LENGTH) -> frozenset[str]:
    return frozenset(
        term
        for term in _ordered_terms(content)
        if len(term) >= minimum_word_length and term not in _STOPWORDS
    )


def _negated_terms(content: str, minimum_word_length: int = _DEFAULT_MINIMUM_WORD_LENGTH) -> frozenset[str]:
    tokens = _ordered_terms(content)
    negated: set[str] = set()
    for index, token in enumerate(tokens):
        if token in _NEGATION_MARKERS:
            window = tokens[index + 1 : index + 1 + _NEGATION_WINDOW]
            negated.update(
                term
                for term in window
                if len(term) >= minimum_word_length and term not in _STOPWORDS and term not in _NEGATION_MARKERS
            )
    return frozenset(negated)


class InsightEngine:
    def detect_patterns(
        self,
        items: tuple[ContextItem, ...],
        *,
        minimum_occurrences: int = _DEFAULT_PATTERN_MINIMUM_OCCURRENCES,
        minimum_word_length: int = _DEFAULT_MINIMUM_WORD_LENGTH,
    ) -> tuple[Insight, ...]:
        term_to_items: dict[str, list[ContextItem]] = defaultdict(list)
        for item in items:
            for term in _distinct_terms(item.content, minimum_word_length):
                term_to_items[term].append(item)

        insights = []
        for term, matching in sorted(term_to_items.items()):
            if len(matching) < minimum_occurrences:
                continue
            confidence = min(1.0, 0.5 + 0.1 * (len(matching) - minimum_occurrences))
            insights.append(
                Insight(
                    insight_type=InsightType.PATTERN,
                    title=f"Recurring theme: '{term}'",
                    observation=f"'{term}' appeared in {len(matching)} separate memories.",
                    basis=InsightBasis.OBSERVED,
                    supporting_memory_ids=tuple(sorted(item.resource_id for item in matching)),
                    subject=term,
                    confidence=confidence,
                )
            )
        return tuple(insights)

    def identify_habits(
        self,
        reflection_items: tuple[ContextItem, ...],
        *,
        minimum_occurrences: int = _DEFAULT_HABIT_MINIMUM_OCCURRENCES,
        minimum_word_length: int = _DEFAULT_MINIMUM_WORD_LENGTH,
    ) -> tuple[Insight, ...]:
        patterns = self.detect_patterns(
            reflection_items, minimum_occurrences=minimum_occurrences, minimum_word_length=minimum_word_length
        )
        return tuple(
            Insight(
                insight_type=InsightType.HABIT,
                title=f"Recurring habit signal: '{pattern.subject}'",
                observation=pattern.observation,
                basis=InsightBasis.INFERRED,
                conclusion=(
                    f"Repeated mentions of '{pattern.subject}' across your reflections may indicate a "
                    "recurring habit or behavioral trend worth noticing."
                ),
                supporting_memory_ids=pattern.supporting_memory_ids,
                subject=pattern.subject,
                confidence=pattern.confidence,
            )
            for pattern in patterns
        )

    def detect_contradictions(
        self,
        preference_items: tuple[ContextItem, ...],
        comparison_items: tuple[ContextItem, ...],
        *,
        minimum_word_length: int = _DEFAULT_MINIMUM_WORD_LENGTH,
    ) -> tuple[Insight, ...]:
        term_to_preferences: dict[str, list[ContextItem]] = defaultdict(list)
        for preference in preference_items:
            for term in _negated_terms(preference.content, minimum_word_length):
                term_to_preferences[term].append(preference)

        insights = []
        for term, negating_preferences in sorted(term_to_preferences.items()):
            for candidate in comparison_items:
                candidate_terms = _distinct_terms(candidate.content, minimum_word_length) - _negated_terms(
                    candidate.content, minimum_word_length
                )
                if term not in candidate_terms:
                    continue
                supporting = tuple(
                    sorted({preference.resource_id for preference in negating_preferences} | {candidate.resource_id})
                )
                insights.append(
                    Insight(
                        insight_type=InsightType.CONTRADICTION,
                        title=f"Possible contradiction around '{term}'",
                        observation=(
                            f"{len(negating_preferences)} preference(s) say to avoid or not do '{term}', but "
                            f"memory #{candidate.resource_id} references '{term}' without that qualification."
                        ),
                        basis=InsightBasis.INFERRED,
                        conclusion=(
                            f"Your stated preference and this memory both reference '{term}' in what look "
                            "like opposing ways - this may be worth reconciling."
                        ),
                        supporting_memory_ids=supporting,
                        subject=term,
                        confidence=_CONTRADICTION_CONFIDENCE,
                    )
                )
        return tuple(insights)

    def measure_alignment(
        self,
        goal_items: tuple[ContextItem, ...],
        recent_activity_items: tuple[ContextItem, ...],
        *,
        minimum_word_length: int = _DEFAULT_MINIMUM_WORD_LENGTH,
    ) -> tuple[Insight, ...]:
        insights = []
        total = len(recent_activity_items)
        for goal_item in goal_items:
            goal_terms = _distinct_terms(goal_item.content, minimum_word_length)
            matching = [
                activity
                for activity in recent_activity_items
                if goal_terms & _distinct_terms(activity.content, minimum_word_length)
            ]
            score = (len(matching) / total) if total else 0.0
            if score >= _ALIGNMENT_WELL_ALIGNED_THRESHOLD:
                verdict = "well-aligned"
            elif score > 0:
                verdict = "drifting"
            else:
                verdict = "not appearing"
            subject = (goal_item.metadata or {}).get("title") or "a goal"
            supporting = tuple(sorted({goal_item.resource_id} | {activity.resource_id for activity in matching}))
            insights.append(
                Insight(
                    insight_type=InsightType.ALIGNMENT,
                    title=f"Alignment: {subject}",
                    observation=f"{len(matching)} of {total} recent activity memories reference this goal's own terms.",
                    basis=InsightBasis.INFERRED,
                    conclusion=f"This goal appears {verdict} with your recent activity ({score:.0%}).",
                    supporting_memory_ids=supporting,
                    subject=subject,
                    confidence=0.6 if total else 0.2,
                )
            )
        return tuple(insights)

    def generate_recommendations(
        self,
        *,
        habit_insights: tuple[Insight, ...] = (),
        contradiction_insights: tuple[Insight, ...] = (),
        alignment_insights: tuple[Insight, ...] = (),
    ) -> tuple[Insight, ...]:
        recommendations = []
        for contradiction in contradiction_insights:
            recommendations.append(
                Insight(
                    insight_type=InsightType.RECOMMENDATION,
                    title=f"Consider reconciling '{contradiction.subject}'",
                    observation=contradiction.observation,
                    basis=InsightBasis.INFERRED,
                    conclusion=f"You might revisit this: {contradiction.conclusion}",
                    supporting_memory_ids=contradiction.supporting_memory_ids,
                    subject=contradiction.subject,
                    confidence=contradiction.confidence,
                )
            )
        for alignment in alignment_insights:
            if not alignment.subject:
                continue
            if "drifting" not in alignment.conclusion and "not appearing" not in alignment.conclusion:
                continue
            recommendations.append(
                Insight(
                    insight_type=InsightType.RECOMMENDATION,
                    title=f"Revisit goal: {alignment.subject}",
                    observation=alignment.observation,
                    basis=InsightBasis.INFERRED,
                    conclusion=(
                        f"'{alignment.subject}' hasn't shown up much in recent activity - consider "
                        "prioritizing it this week or explicitly deciding to pause it."
                    ),
                    supporting_memory_ids=alignment.supporting_memory_ids,
                    subject=alignment.subject,
                    confidence=alignment.confidence,
                )
            )
        for habit in habit_insights:
            recommendations.append(
                Insight(
                    insight_type=InsightType.RECOMMENDATION,
                    title=f"Notice the pattern: '{habit.subject}'",
                    observation=habit.observation,
                    basis=InsightBasis.INFERRED,
                    conclusion=f"This has come up repeatedly in your reflections. {habit.conclusion}",
                    supporting_memory_ids=habit.supporting_memory_ids,
                    subject=habit.subject,
                    confidence=habit.confidence,
                )
            )
        return tuple(recommendations)

    def generate_periodic_reflection(
        self,
        *,
        period: InsightPeriod,
        window_items: tuple[ContextItem, ...],
        pattern_insights: tuple[Insight, ...] = (),
        habit_insights: tuple[Insight, ...] = (),
        alignment_insights: tuple[Insight, ...] = (),
    ) -> Insight:
        insight_supporting_ids = {
            memory_id
            for insight in (*pattern_insights, *habit_insights, *alignment_insights)
            for memory_id in insight.supporting_memory_ids
        }
        supporting = tuple(sorted({item.resource_id for item in window_items} | insight_supporting_ids))
        themes = sorted({pattern.subject for pattern in pattern_insights if pattern.subject})
        highlights = ", ".join(themes) if themes else "no strong recurring themes"
        return Insight(
            insight_type=InsightType.PERIODIC_REFLECTION,
            title=f"{period.value.capitalize()} reflection",
            observation=f"{len(window_items)} memories were recorded during this {period.value} window.",
            basis=InsightBasis.INFERRED,
            conclusion=f"Recurring themes this {period.value}: {highlights}.",
            supporting_memory_ids=supporting,
            subject=period.value,
            confidence=0.7 if window_items else 0.0,
        )

    def synthesize_profile(self, *, recent_insights: tuple[Insight, ...]) -> Insight:
        supporting = tuple(sorted({memory_id for insight in recent_insights for memory_id in insight.supporting_memory_ids}))
        counts = Counter(insight.insight_type.value for insight in recent_insights)
        breakdown = ", ".join(f"{count} {type_}" for type_, count in sorted(counts.items())) if counts else "none yet"
        conclusion = "; ".join(insight.title for insight in recent_insights[:5]) or (
            "Not enough data yet to characterize a stable profile."
        )
        return Insight(
            insight_type=InsightType.PROFILE_SUMMARY,
            title="Personal profile update",
            observation=f"Profile synthesized from {len(recent_insights)} recent insight(s): {breakdown}.",
            basis=InsightBasis.INFERRED,
            conclusion=conclusion,
            supporting_memory_ids=supporting,
            subject="profile",
            confidence=min(1.0, 0.2 + 0.1 * len(recent_insights)),
        )
