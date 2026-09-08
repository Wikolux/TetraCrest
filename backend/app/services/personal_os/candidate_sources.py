"""Candidate sources (P5 §26): turns already-existing Personal OS records
into priority.py's own CandidateItem shape - the bridge §26 requires
("the priority engine may consider unfinished commitments, active
experiments, recent patterns, recommendations, current intent... but it
must not duplicate those repositories").

Every function here is a pure, deterministic transformation of records
this package already owns (DailyIntent, Mission, Pattern, Experiment) -
none of them read a repository themselves; the caller (priority_flow.py)
gathers records via the existing repositories and passes them in here.
Nothing in this module invents a factor value from nothing: where a
source record carries no real signal for a factor, that factor is left
at CandidateItem's own honest default (0.0), never guessed.
"""

from dataclasses import replace

from app.services.personal_os.daily_intent import DailyIntent
from app.services.personal_os.experiment import Experiment
from app.services.personal_os.living_day import LivingDayState
from app.services.personal_os.mission import Mission
from app.services.personal_os.pattern import Pattern
from app.services.personal_os.priority import CandidateItem
from app.services.personal_os.shared.types import ExperimentStatus, LifeDomain, PatternStatus, PriorityDirection

# A moderate, documented default (never a precise, fabricated valuation)
# reflecting only "this is an active, user-created mission's own next
# step" - real strategic value the user can always override by how they
# describe the mission, never inferred from mission content this module
# does not actually parse.
_MISSION_STRATEGIC_VALUE_DEFAULT = 0.6
_PATTERN_MOMENTUM_DEFAULT = 0.5
_EXPERIMENT_REVIEW_MOMENTUM_DEFAULT = 0.5

_DOMAIN_VALUES = {domain.value for domain in LifeDomain}


def _domain_from_focus_area(focus_area: str) -> LifeDomain | None:
    """Only maps when focus_area is literally a LifeDomain value - never
    guesses from free text (that would be exactly the "invented data"
    §26/§28 rule out; an unmapped focus_area simply yields domain=None,
    honestly)."""
    return LifeDomain(focus_area) if focus_area in _DOMAIN_VALUES else None


def from_living_day_state(state: LivingDayState) -> tuple[CandidateItem, ...]:
    """P6.2: the living day's own ACTIVE activities, superseding
    from_daily_intent() once the day has actually started evolving - a
    caller with a LivingDayState uses this instead of (never in addition
    to) from_daily_intent(), since every morning-seeded activity is
    already folded into state.activities (living_day.reconstruct()'s own
    job). COMPLETED/POSTPONED/HELD/REMOVED activities are deliberately
    excluded (P6.3's own "postponed work is not incorrectly resurfaced,"
    "completed work is not recommended again"): they still exist in
    state.activities for history and reporting, just not as something
    left to prioritize. Unexpected-event-originated activities are also
    excluded here - reconstruct() itself always records an
    UNEXPECTED_EVENT as COMPLETED (an event that already happened is not
    a candidate for future ranking; its only effect on priority is the
    available-time reduction that separately already happened), so
    state.active_activities already excludes every unexpected-event
    activity without this module needing its own second check."""
    return tuple(
        CandidateItem(
            item_id=activity.activity_id,
            description=activity.description,
            domain=activity.domain,
            deadline=activity.deadline,
            is_current_intent=True,
            estimated_hours=activity.estimated_hours,
            source="living_day",
            source_id=activity.activity_id,
        )
        for activity in state.active_activities
    )


def from_daily_intent(intent: DailyIntent) -> tuple[CandidateItem, ...]:
    """Today's own planned activities - always is_current_intent=True,
    since these are literally what the user said they intend to do
    today (§7's own CURRENT_USER_INTENT factor)."""
    return tuple(
        CandidateItem(
            item_id=f"intent:{intent.intent_date.isoformat()}:{activity.description}",
            description=activity.description,
            domain=_domain_from_focus_area(activity.focus_area),
            deadline=activity.deadline,
            is_current_intent=True,
            estimated_hours=activity.estimated_hours,
            source="daily_intent",
            source_id=activity.description,
        )
        for activity in intent.planned_activities
    )


def from_missions(missions: tuple[Mission, ...]) -> tuple[CandidateItem, ...]:
    """One candidate per active mission's own stated next_step - missions
    with no next_step yet contribute nothing (there is no concrete action
    to rank)."""
    items = []
    for mission in missions:
        if not mission.next_step:
            continue
        items.append(
            CandidateItem(
                item_id=f"mission:{mission.mission_id}",
                description=mission.next_step,
                domain=mission.domain,
                deadline=mission.target_date,
                strategic_value=_MISSION_STRATEGIC_VALUE_DEFAULT,
                financial_value=0.4 if mission.budget else 0.0,
                source="mission",
                source_id=mission.mission_id,
            )
        )
    return tuple(items)


def from_pattern_recommendations(patterns: tuple[Pattern, ...]) -> tuple[CandidateItem, ...]:
    """Confirmed patterns with an attached, user-approved recommendation
    (§26's own "recommendations") - never a pattern still pending
    confirmation or one the user rejected/corrected (only CONFIRMED
    patterns reach this far)."""
    items = []
    for pattern in patterns:
        if pattern.status != PatternStatus.CONFIRMED or pattern.recommendation is None:
            continue
        items.append(
            CandidateItem(
                item_id=f"pattern:{pattern.pattern_id}",
                description=pattern.recommendation.statement,
                growth_value=_PATTERN_MOMENTUM_DEFAULT,
                momentum=_PATTERN_MOMENTUM_DEFAULT,
                source="pattern",
                source_id=pattern.pattern_id,
            )
        )
    return tuple(items)


def apply_adopted_priority_effects(
    candidates: tuple[CandidateItem, ...],
    *,
    domain_effects: dict[LifeDomain, PriorityDirection],
    mission_effects: dict[str, PriorityDirection],
    boost_magnitude: float,
) -> tuple[CandidateItem, ...]:
    """P7.11: the one place an ADOPTED Adaptation's structured
    PRIORITY_ADJUSTMENT effect actually touches a candidate - a bounded
    nudge to `momentum` (the same factor from_pattern_recommendations()
    already uses for a non-hard-fact signal), never a new factor, never
    a rewrite of `calculate_score()`/`rank_candidates()`. `domain_effects`
    /`mission_effects` are already-resolved {key: direction} maps (built
    by the caller from whatever is currently ADOPTED - see
    priority_flow.py); this function itself reads no repository and
    knows nothing about Adaptation's own lifecycle.

    A mission-specific effect takes precedence over a domain-level one
    for the same candidate (the more specific target wins) - the only
    precedence rule this function needs, since a candidate can match at
    most one of the two maps' keys by construction (item_id/source_id
    vs. domain are different fields). Deliberately never applied to
    is_current_intent candidates (from_daily_intent()/
    from_living_day_state() never pass through here - see
    priority_flow.gather_non_intent_candidates()): a learned preference
    nudges discretionary candidates (missions, pattern recommendations,
    experiments), it never re-weights what the user already explicitly
    said they intend to do today."""
    if not domain_effects and not mission_effects:
        return candidates

    adjusted = []
    for candidate in candidates:
        direction: PriorityDirection | None = None
        if candidate.source == "mission" and candidate.source_id in mission_effects:
            direction = mission_effects[candidate.source_id]
        elif candidate.domain is not None and candidate.domain in domain_effects:
            direction = domain_effects[candidate.domain]

        if direction is None:
            adjusted.append(candidate)
            continue

        delta = boost_magnitude if direction == PriorityDirection.BOOST else -boost_magnitude
        new_momentum = min(1.0, max(0.0, candidate.momentum + delta))
        adjusted.append(replace(candidate, momentum=new_momentum))

    return tuple(adjusted)


def from_experiments(experiments: tuple[Experiment, ...]) -> tuple[CandidateItem, ...]:
    """Experiments ready for the user's own review (§26's own "active
    experiments") - an experiment still ACTIVE and not yet due is not a
    candidate; there is nothing to act on yet."""
    items = []
    for experiment in experiments:
        if experiment.status != ExperimentStatus.READY_FOR_REVIEW:
            continue
        items.append(
            CandidateItem(
                item_id=f"experiment:{experiment.experiment_id}",
                description=f"Review your experiment: {experiment.adjustment}",
                deadline=experiment.review_date,
                momentum=_EXPERIMENT_REVIEW_MOMENTUM_DEFAULT,
                source="experiment",
                source_id=experiment.experiment_id,
            )
        )
    return tuple(items)
