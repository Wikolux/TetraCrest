"""Priority Intelligence (P5 §7-§10): a deterministic evaluation of
candidate items using contextual factors - never a permanent hierarchy
(§7's own explicit "career > business > study > finance" anti-example).

The engine applies the SAME named weights (PriorityConfig) to every
candidate regardless of domain - nothing in this module gives one
LifeDomain a structural advantage over another. What actually
differentiates two candidates is their own factor VALUES (how urgent,
how strategically valuable, how close the deadline), which a caller
supplies per item from real, current context - exactly the "depends on
what the two things are at the moment" rule §7 states. Day-mode alignment
is the one factor that shifts with context (day_mode.py's own
DAY_MODE_DOMAIN_BOOST/DAY_MODE_SUPPRESSES_WORK tables), and even that
only re-weights ranking for today, never rewrites a domain's underlying
importance (§12's own "does not permanently change the user's life
priorities").

Every number here is a plain, inspectable calculation - calculate_score()
and rank_candidates() import neither RuntimeAdapter nor PromptBuilder
(enforced by test_personal_os_architecture.py), matching §27's own
"do not let an LLM secretly determine priority mathematics." explain()
builds the FACT/INFERENCE/RECOMMENDATION triad §8 requires as plain,
deterministic text; a caller (priority_flow.py) may ask the Runtime to
rephrase that text conversationally, but never to recompute it.
"""

from dataclasses import dataclass, field
from datetime import date

from app.services.personal_os.day_mode import DAY_MODE_DOMAIN_BOOST, DAY_MODE_SUPPRESSES_WORK, DayMode
from app.services.personal_os.shared.types import LifeDomain, PriorityFactor

_WORK_DOMAINS = frozenset(
    {LifeDomain.CAREER, LifeDomain.BUSINESS, LifeDomain.TECHNICAL_PROJECTS, LifeDomain.STUDY, LifeDomain.PERSONAL_BRAND, LifeDomain.FINANCE_INVESTMENTS}
)


@dataclass(frozen=True)
class PriorityConfig:
    """Every weight and threshold this module uses, named and
    overridable - never a bare literal buried in calculate_score()'s own
    body, the same discipline pattern_detectors.PatternDetectionConfig
    already established."""

    core_count: int = 5
    optional_count: int = 2
    urgency_weight: float = 1.0
    deadline_weight: float = 0.8
    financial_value_weight: float = 0.7
    strategic_value_weight: float = 0.9
    opportunity_value_weight: float = 0.7
    growth_value_weight: float = 0.5
    momentum_weight: float = 0.4
    current_user_intent_weight: float = 1.0
    consequence_of_delay_weight: float = 0.9
    available_time_weight: float = 0.5
    day_mode_alignment_weight: float = 0.8
    urgency_near_days: int = 3
    urgency_soon_days: int = 7
    day_mode_boost: float = 0.3
    day_mode_suppress_penalty: float = 0.4


@dataclass(frozen=True)
class CandidateItem:
    """One thing the Priority Engine might rank - deliberately not a new
    task-tracking record (§26, §28): a candidate carries only the factor
    inputs the engine needs, and `source`/`source_id` trace it back to
    whatever already-existing record produced it (a DailyIntent activity,
    a Mission's next_step, a Pattern, an Experiment...), so this module
    never becomes a second place candidate content actually lives."""

    item_id: str
    description: str
    domain: LifeDomain | None = None
    deadline: date | None = None
    financial_value: float = 0.0
    strategic_value: float = 0.0
    opportunity_value: float = 0.0
    growth_value: float = 0.0
    momentum: float = 0.0
    is_current_intent: bool = False
    consequence_of_delay: float = 0.0
    estimated_hours: float | None = None
    source: str = "manual"
    source_id: str = ""

    def __post_init__(self) -> None:
        if not self.description:
            raise ValueError("CandidateItem.description is required")
        for name in ("financial_value", "strategic_value", "opportunity_value", "growth_value", "momentum", "consequence_of_delay"):
            value = getattr(self, name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"CandidateItem.{name} must be within [0.0, 1.0], got {value}")


@dataclass(frozen=True)
class PriorityScore:
    """One candidate's own evaluation - factor_values keeps every factor
    inspectable individually (§8's own "the underlying priority factors
    should remain deterministic and inspectable"), never collapsed into
    just the final number."""

    item: CandidateItem
    total: float
    factor_values: dict[PriorityFactor, float] = field(default_factory=dict)


@dataclass(frozen=True)
class PriorityExplanation:
    """§8's own required FACT/INFERENCE/RECOMMENDATION distinction, kept
    structurally separate the same way reasoning.py separates ObservedFact
    from Hypothesis from GrowthRecommendation - never merged into one
    prose blob before this point."""

    facts: tuple[str, ...]
    inference: str
    recommendation: str


@dataclass(frozen=True)
class PriorityRanking:
    core: tuple[PriorityScore, ...]
    optional: tuple[PriorityScore, ...]
    day_mode: DayMode | None = None


def _urgency(deadline: date | None, today: date, config: PriorityConfig) -> float:
    if deadline is None:
        return 0.0
    days = (deadline - today).days
    if days <= 0:
        return 1.0
    if days <= config.urgency_near_days:
        return 0.6
    if days <= config.urgency_soon_days:
        return 0.3
    return 0.1


def _deadline_factor(deadline: date | None, today: date, config: PriorityConfig) -> float:
    if deadline is None:
        return 0.0
    days = (deadline - today).days
    return 1.0 if days <= config.urgency_soon_days else 0.3


def _available_time_factor(estimated_hours: float | None, available_hours: float) -> float:
    if estimated_hours is None:
        return 0.5
    return 1.0 if estimated_hours <= available_hours else 0.2


def _day_mode_alignment(domain: LifeDomain | None, day_mode: DayMode | None, config: PriorityConfig) -> float:
    if day_mode is None or domain is None:
        return 0.5
    boosted_domains = DAY_MODE_DOMAIN_BOOST.get(day_mode.kind, ())
    if domain in boosted_domains:
        return min(1.0, 0.5 + config.day_mode_boost)
    if day_mode.kind in DAY_MODE_SUPPRESSES_WORK and domain in _WORK_DOMAINS:
        return max(0.0, 0.5 - config.day_mode_suppress_penalty)
    return 0.5


def calculate_score(
    item: CandidateItem, *, today: date, available_hours: float, day_mode: DayMode | None, config: PriorityConfig | None = None
) -> PriorityScore:
    """Pure function: same item + same context in, same PriorityScore
    out (§27, §18-style determinism every deterministic Personal OS
    calculation already follows)."""
    config = config or PriorityConfig()

    factor_values = {
        PriorityFactor.URGENCY: _urgency(item.deadline, today, config),
        PriorityFactor.DEADLINE: _deadline_factor(item.deadline, today, config),
        PriorityFactor.FINANCIAL_VALUE: item.financial_value,
        PriorityFactor.STRATEGIC_VALUE: item.strategic_value,
        PriorityFactor.OPPORTUNITY_VALUE: item.opportunity_value,
        PriorityFactor.GROWTH_VALUE: item.growth_value,
        PriorityFactor.MOMENTUM: item.momentum,
        PriorityFactor.CURRENT_USER_INTENT: 1.0 if item.is_current_intent else 0.0,
        PriorityFactor.CONSEQUENCE_OF_DELAY: item.consequence_of_delay,
        PriorityFactor.AVAILABLE_TIME: _available_time_factor(item.estimated_hours, available_hours),
        PriorityFactor.DAY_MODE_ALIGNMENT: _day_mode_alignment(item.domain, day_mode, config),
    }
    weights = {
        PriorityFactor.URGENCY: config.urgency_weight,
        PriorityFactor.DEADLINE: config.deadline_weight,
        PriorityFactor.FINANCIAL_VALUE: config.financial_value_weight,
        PriorityFactor.STRATEGIC_VALUE: config.strategic_value_weight,
        PriorityFactor.OPPORTUNITY_VALUE: config.opportunity_value_weight,
        PriorityFactor.GROWTH_VALUE: config.growth_value_weight,
        PriorityFactor.MOMENTUM: config.momentum_weight,
        PriorityFactor.CURRENT_USER_INTENT: config.current_user_intent_weight,
        PriorityFactor.CONSEQUENCE_OF_DELAY: config.consequence_of_delay_weight,
        PriorityFactor.AVAILABLE_TIME: config.available_time_weight,
        PriorityFactor.DAY_MODE_ALIGNMENT: config.day_mode_alignment_weight,
    }
    weighted_sum = sum(factor_values[f] * weights[f] for f in factor_values)
    total_weight = sum(weights.values())
    total = weighted_sum / total_weight if total_weight else 0.0

    return PriorityScore(item=item, total=total, factor_values=factor_values)


def rank_candidates(
    items: tuple[CandidateItem, ...],
    *,
    today: date,
    available_hours: float,
    day_mode: DayMode | None = None,
    config: PriorityConfig | None = None,
) -> PriorityRanking:
    """§10: Core 5 + Optional 2 by default - never a full task dump.
    Ties broken by item_id for a stable, deterministic order (never
    dict/set iteration order). RECOVERY/FAMILY_FOCUSED day modes reduce
    how many optional items are worth surfacing at all (§12) - core_count
    itself is never reduced, since the core priorities remain real even
    on a lighter day; only the optional surplus shrinks."""
    config = config or PriorityConfig()
    from app.services.personal_os.day_mode import DAY_MODE_REDUCES_OPTIONAL

    scores = [calculate_score(item, today=today, available_hours=available_hours, day_mode=day_mode, config=config) for item in items]
    scores.sort(key=lambda s: (-s.total, s.item.item_id))

    optional_count = 0 if (day_mode is not None and day_mode.kind in DAY_MODE_REDUCES_OPTIONAL) else config.optional_count
    core = tuple(scores[: config.core_count])
    optional = tuple(scores[config.core_count : config.core_count + optional_count])
    return PriorityRanking(core=core, optional=optional, day_mode=day_mode)


@dataclass(frozen=True)
class OverrideResult:
    """A user adjustment applied to a candidate set (§13, §21, §30) -
    never deletes a candidate's underlying record (this module never
    touches any repository; candidates are re-derived fresh next time
    regardless). held_items are the ones excluded from today's ranking
    because their domain is on hold and they are not urgent enough to
    need surfacing anyway - returned, never silently dropped, so a
    caller can present them as "what can safely move." surfaced_despite_
    hold are held-domain items urgent enough (deadline today or overdue)
    that hiding them would be dishonest, not merely inconvenient (§30's
    own "surfaces only genuinely time-sensitive items if necessary")."""

    ranking: PriorityRanking
    held_domains: tuple[LifeDomain, ...]
    held_items: tuple[CandidateItem, ...]
    surfaced_despite_hold: tuple[PriorityScore, ...]


_URGENT_ENOUGH_TO_OVERRIDE_HOLD = 0.9


def apply_override(
    candidates: tuple[CandidateItem, ...],
    *,
    today: date,
    available_hours: float,
    day_mode: DayMode | None = None,
    hold_domains: tuple[LifeDomain, ...] = (),
    config: PriorityConfig | None = None,
) -> OverrideResult:
    """Re-ranks after the user asks to hold one or more domains for
    today (e.g. "hold all work today, family day") - the OS adapts
    (§13), it does not argue, delete, or mark anything a failure (§9,
    §21)."""
    config = config or PriorityConfig()
    eligible: list[CandidateItem] = []
    held_items: list[CandidateItem] = []
    held_but_urgent: list[CandidateItem] = []

    for item in candidates:
        if item.domain in hold_domains:
            if _urgency(item.deadline, today, config) >= _URGENT_ENOUGH_TO_OVERRIDE_HOLD:
                held_but_urgent.append(item)
            else:
                held_items.append(item)
                continue
        eligible.append(item)

    ranking = rank_candidates(tuple(eligible), today=today, available_hours=available_hours, day_mode=day_mode, config=config)
    surfaced = tuple(
        calculate_score(item, today=today, available_hours=available_hours, day_mode=day_mode, config=config) for item in held_but_urgent
    )
    return OverrideResult(ranking=ranking, held_domains=tuple(hold_domains), held_items=tuple(held_items), surfaced_despite_hold=surfaced)


_FACTOR_LABELS: dict[PriorityFactor, str] = {
    PriorityFactor.URGENCY: "it is time-sensitive",
    PriorityFactor.DEADLINE: "it has a near-term deadline",
    PriorityFactor.FINANCIAL_VALUE: "it has real financial value",
    PriorityFactor.STRATEGIC_VALUE: "it is strategically important right now",
    PriorityFactor.OPPORTUNITY_VALUE: "delaying it risks losing an opportunity",
    PriorityFactor.GROWTH_VALUE: "it supports your growth",
    PriorityFactor.MOMENTUM: "you have momentum on it",
    PriorityFactor.CURRENT_USER_INTENT: "it matches what you said you want to focus on today",
    PriorityFactor.CONSEQUENCE_OF_DELAY: "delaying it has real consequences",
    PriorityFactor.AVAILABLE_TIME: "it fits the time you have available",
    PriorityFactor.DAY_MODE_ALIGNMENT: "it fits today's mode",
}
_NOTABLE_FACTOR_THRESHOLD = 0.6


def explain(score: PriorityScore, *, today: date) -> PriorityExplanation:
    """Deterministic, plain-text FACT/INFERENCE/RECOMMENDATION (§8) -
    built directly from the same factor_values the ranking itself used,
    never re-derived or guessed. This is the text priority_flow.py may
    hand to the Runtime for conversational rephrasing - the Runtime
    receives this, it never recomputes it."""
    facts = []
    if score.item.deadline is not None:
        if score.item.deadline <= today:
            facts.append(f"The deadline is {score.item.deadline} (today or already passed).")
        else:
            facts.append(f"The deadline is {score.item.deadline}.")
    notable = [factor for factor, value in score.factor_values.items() if value >= _NOTABLE_FACTOR_THRESHOLD and factor not in (PriorityFactor.DEADLINE,)]
    for factor in notable:
        facts.append(_FACTOR_LABELS[factor].capitalize() + ".")
    if not facts:
        facts.append("No single factor stands out strongly; this ranked based on its overall combination of factors.")

    reasons = ", ".join(_FACTOR_LABELS[f] for f in notable) if notable else "its overall combination of factors"
    inference = f"This appears to deserve attention today because {reasons}."
    recommendation = f'I suggest placing "{score.item.description}" among today\'s priorities.'

    return PriorityExplanation(facts=tuple(facts), inference=inference, recommendation=recommendation)
