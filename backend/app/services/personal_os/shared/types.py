"""Personal OS (Application layer) - shared vocabulary.

Personal OS is an Application, not a Capability Pack (see
docs/00_OVERVIEW/VERSION_1_PLATFORM_BASELINE.md's Application Layer
Definition): it does not register a SpecialistAgent, does not declare an
AgentCapability, and does not mint its own Memory Framework namespace.
Everything in this package is either (a) a plain Python domain object
describing Personal OS's own orchestration state (Daily Intent, a
reconciliation record, a plan recommendation), held via the repository
interface in repository.py rather than AgentMemory, or (b) a read-only
consumer of CP-01/CP-02's own memory content via the existing
MemoryAdapter/AgentMemory contract - never a direct import of either
pack's specialist code (enforced by test_personal_os_architecture.py).

These enums are the closed vocabulary every other module in this package
builds on.
"""

from enum import StrEnum


class DayType(StrEnum):
    """What kind of day the user intends to have (§3 of the Personal OS
    build spec) - deliberately not a productivity-only taxonomy. REST is
    a first-class, equally valid value, never a fallback or an absence."""

    WORK = "work"
    STUDY = "study"
    PROJECT = "project"
    MIXED = "mixed"
    REST = "rest"
    OTHER = "other"


class IntentSource(StrEnum):
    """Where one field of a DailyIntent came from - never conflated, so a
    caller can always tell a carried-over fact from a fresh user
    statement from a heuristic guess."""

    CARRIED_OVER = "carried_over"
    USER_EXPLICIT = "user_explicit"
    HEURISTIC_PARSE = "heuristic_parse"
    SYSTEM_DEFAULT = "system_default"


class Confidence(StrEnum):
    """How sure Personal OS is about one field's value - a closed,
    coarse scale (never a fabricated numeric probability) matching the
    same "confidence must reflect evidence quality" discipline every
    Capability Pack specialist already follows."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReconciliationStatus(StrEnum):
    """The eight statuses §6 of the build spec requires. "Not completed"
    is never auto-mapped to INCOMPLETE by default - UNKNOWN is the
    honest default when evidence is insufficient to classify at all."""

    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    SUPERSEDED = "superseded"
    RESTED = "rested"
    UNKNOWN = "unknown"


class ObservationBasis(StrEnum):
    """§10's fact/inference/hypothesis/recommendation distinction,
    structural rather than conventional: a caller reading a Personal OS
    reasoning artifact can always tell which of these five it is looking
    at from its own type, never from prose alone.

    USER_EXPLANATION (Evening Reflection, P2 §4) is a distinct fifth
    basis, additive to the original four - a reason the user themselves
    gave is neither an ObservedFact (it is an interpretation, even when
    true) nor a system-generated Hypothesis (it did not originate with
    Personal OS's own reasoning) - conflating the two would risk exactly
    what §4 forbids: presenting an inference as settled, or a user's own
    account as a system judgment."""

    OBSERVED_FACT = "observed_fact"
    INFERRED_PATTERN = "inferred_pattern"
    USER_EXPLANATION = "user_explanation"
    HYPOTHESIS = "hypothesis"
    RECOMMENDATION = "recommendation"


class RecommendationKind(StrEnum):
    """The named adaptive-planning actions §7 lists - a closed set so a
    recommendation is always one of these, never free text standing in
    for a decision Personal OS didn't actually make."""

    MOVE = "move"
    REPRIORITIZE = "reprioritize"
    POSTPONE = "postpone"
    SPLIT = "split"
    REDUCE_SCOPE = "reduce_scope"
    RESEQUENCE = "resequence"
    PROTECT_REST = "protect_rest"
    ALLOCATE_MORE_TIME = "allocate_more_time"


class PatternType(StrEnum):
    """The smallest useful initial set (P3 §4) - deliberately not every
    conceivable behavioural analytic. Each has its own detector in
    pattern_detectors.py; adding a sixth type is a new StrEnum member and
    a new detector function, never a change to Pattern's own shape."""

    REPEATED_POSTPONEMENT = "repeated_postponement"
    ESTIMATION_ACCURACY = "estimation_accuracy"
    RECURRING_BLOCKER = "recurring_blocker"
    PRIORITY_CHANGE = "priority_change"
    COMPLETION_PATTERN = "completion_pattern"


class PatternStatus(StrEnum):
    """A Pattern's own lifecycle (P3 §10, §11) - never treated as
    permanent truth without one of these. OBSERVED is the initial,
    system-only state (detected, not yet surfaced); PENDING_CONFIRMATION
    is set the moment it is actually shown to the user; CONFIRMED/
    CORRECTED/DISMISSED are the three possible user responses (§11);
    SUPERSEDED marks a pattern a later, more complete detection run has
    replaced - the same append-only "a revision is a new entry" discipline
    every other durable Personal OS record already follows, applied to
    status transitions instead of content."""

    OBSERVED = "observed"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    DISMISSED = "dismissed"
    SUPERSEDED = "superseded"


class UserPatternResponse(StrEnum):
    """How the user may respond when a Pattern is surfaced (P3 §11) -
    "defer judgment" is a real, first-class response (PatternStatus stays
    PENDING_CONFIRMATION, never silently advanced to CONFIRMED by
    default), not merely the absence of a reply."""

    CONFIRM = "confirm"
    REJECT = "reject"
    CORRECT = "correct"
    DEFER = "defer"


class ExperimentStatus(StrEnum):
    """An Experiment's own lifecycle (P3 §13, extended P4 §3) - the three
    P3 values (PROPOSED/ACTIVE/REVIEWED) are unchanged; P4 adds the
    explicit approval boundary (§4) and the terminal user-decision states
    (§14) the P3 lifecycle never needed since P3 never activated an
    experiment or reviewed one against real evidence.

    Valid transitions (enforced in experiment_flow.py, not just named
    here): PROPOSED -> APPROVED | STOPPED (explicit rejection) |
    unchanged (DEFER); APPROVED -> ACTIVE; ACTIVE -> READY_FOR_REVIEW |
    EXPIRED; READY_FOR_REVIEW -> REVIEWED | EXPIRED; REVIEWED -> KEPT |
    MODIFIED | STOPPED | ACTIVE (CONTINUE, with an extended review_date).
    Every transition is a new persisted version under the same
    experiment_id (append-only, matching Pattern's own convention) - the
    full lifecycle is always retrievable as history, never overwritten."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    ACTIVE = "active"
    READY_FOR_REVIEW = "ready_for_review"
    REVIEWED = "reviewed"
    KEPT = "kept"
    MODIFIED = "modified"
    STOPPED = "stopped"
    EXPIRED = "expired"


class ExperimentOutcome(StrEnum):
    """The deterministic result of comparing an Experiment's measurement
    against its baseline (P4 §11) - never an LLM's subjective judgement
    (§11's own explicit instruction). INSUFFICIENT_DATA is distinct from
    UNCHANGED: the former means there was not enough evidence to compare
    at all (zero observations on one side); the latter means there was
    evidence and it showed no notable movement. INCONCLUSIVE is distinct
    from both: the magnitude of change would otherwise read as IMPROVED
    or WORSENED, but the sample is too small to say so with more than
    LOW confidence (§10's own "early signal" caution) - see
    experiment_measurement.py's classify_outcome()."""

    IMPROVED = "improved"
    UNCHANGED = "unchanged"
    WORSENED = "worsened"
    INCONCLUSIVE = "inconclusive"
    INSUFFICIENT_DATA = "insufficient_data"


class ExperimentUserDecision(StrEnum):
    """What the user chooses to do after an experiment is reviewed (P4
    §13) - kept structurally distinct from ExperimentStatus itself
    because the decision is the user's own input, while the status is
    Personal OS's own resulting state (the same fact/response separation
    UserPatternResponse already established for Pattern confirmation)."""

    KEEP = "keep"
    MODIFY = "modify"
    STOP = "stop"
    CONTINUE = "continue"
    DEFER = "defer"


class LifeDomain(StrEnum):
    """The ten named areas of the user's life Personal State tracks (P5
    §3) - a closed-but-growable enum, the same discipline PatternType
    already established: adding an eleventh domain is a new member here,
    never a magic string threaded through the rest of the package.

    This is a DIFFERENT concept from BriefDomain (brief.py) - BriefDomain
    names thirteen *report sections* an Intelligence Brief renders
    through; LifeDomain names areas of the user's actual life that carry
    their own activation state (LifeDomainStatus) and history. The two
    enums share no members and are never substituted for one another."""

    CAREER = "career"
    STUDY = "study"
    TECHNICAL_PROJECTS = "technical_projects"
    BUSINESS = "business"
    FINANCE_INVESTMENTS = "finance_investments"
    PERSONAL_BRAND = "personal_brand"
    FAMILY = "family"
    LONG_TERM_GOALS = "long_term_goals"
    EXPERIMENTS = "experiments"
    COMMITMENTS = "commitments"


class LifeDomainStatus(StrEnum):
    """A LifeDomainState's own activation status (P5 §4) - deliberately
    not a permanent on/off flag. NOT_STARTED is the honest default for a
    domain the user has never engaged with; DORMANT is distinct from
    PAUSED (paused = the user deliberately set it aside; dormant = it has
    simply had no activity or review in a long time, a fact Personal OS
    can observe, never a user decision it invents on their behalf)."""

    NOT_STARTED = "not_started"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    DORMANT = "dormant"


class LifeDomainClassification(StrEnum):
    """Whether a domain is normally persistent, seasonal, or created only
    as needed (P5 §4) - the user's own explicit classification, recorded
    as data (life_domain.py's DEFAULT_CLASSIFICATION table) rather than
    as branching logic, and never used to imply a permanent priority
    ranking (§7's own explicit "not a permanent hierarchy" instruction) -
    classification says how a domain tends to behave over time, not how
    important it is on any given day."""

    PERSISTENT = "persistent"
    SEASONAL = "seasonal"
    DYNAMIC = "dynamic"


class DayModeKind(StrEnum):
    """The day-mode categories P5 §11 names, plus CUSTOM - an open
    escape hatch (DayMode.custom_label) for a day-mode the user names
    themselves, since §11 explicitly requires "the model should allow a
    user-defined day mode" and a closed enum alone cannot do that."""

    STRUCTURED_PRODUCTIVE = "structured_productive"
    FLEXIBLE = "flexible"
    RECOVERY = "recovery"
    FAMILY_FOCUSED = "family_focused"
    PROJECT_FOCUSED = "project_focused"
    STUDY_FOCUSED = "study_focused"
    CUSTOM = "custom"


class PriorityFactor(StrEnum):
    """The contextual factors the Priority Engine evaluates (P5 §7) -
    named and enumerable specifically so a PriorityExplanation can cite
    exactly which factors contributed to a ranking, never a bare number
    with no traceable basis. This is a fixed *vocabulary* of factors, not
    a fixed *hierarchy* - §7's own explicit "not a permanent ranking"
    instruction governs how these are weighted per candidate, never which
    domain wins by default."""

    URGENCY = "urgency"
    DEADLINE = "deadline"
    FINANCIAL_VALUE = "financial_value"
    STRATEGIC_VALUE = "strategic_value"
    OPPORTUNITY_VALUE = "opportunity_value"
    GROWTH_VALUE = "growth_value"
    MOMENTUM = "momentum"
    CURRENT_USER_INTENT = "current_user_intent"
    CONSEQUENCE_OF_DELAY = "consequence_of_delay"
    AVAILABLE_TIME = "available_time"
    DAY_MODE_ALIGNMENT = "day_mode_alignment"


class MissionStatus(StrEnum):
    """A Mission's own lifecycle (P5 §15) - DRAFT is a mission the user
    has started describing but not yet committed to; CANCELLED is
    distinct from COMPLETED so "we stopped pursuing this" is never
    conflated with "we achieved this.\""""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AutonomyAction(StrEnum):
    """The seven action levels P5 §18 names, ordered from least to most
    consequential. RESERVE and EXECUTE are the two levels that always
    require an explicit, scoped, non-expired AutonomyGrant (autonomy.py's
    own REQUIRES_EXPLICIT_AUTHORIZATION set) - every level below that is
    allowed by default, since observing, researching, preparing,
    recommending, and asking are all reversible and non-consequential on
    their own."""

    OBSERVE = "observe"
    RESEARCH = "research"
    PREPARE = "prepare"
    RECOMMEND = "recommend"
    ASK = "ask"
    RESERVE = "reserve"
    EXECUTE = "execute"


class DayEventType(StrEnum):
    """The nine capabilities P6.1 names, as a closed, append-only event
    vocabulary - one DayEvent is one real thing that happened, never a
    whole-day snapshot. living_day.py's reconstruct() folds a sequence of
    these, in order, into the current LivingDayState; the events
    themselves are never edited or replaced, only appended to (the same
    append-only discipline every durable Personal OS record already
    follows, applied here to discrete facts rather than whole-object
    versions, since a day is a sequence of things that happened, not one
    entity with a single evolving status)."""

    ACTIVITY_ADDED = "activity_added"
    ACTIVITY_COMPLETED = "activity_completed"
    ACTIVITY_POSTPONED = "activity_postponed"
    ACTIVITY_HELD = "activity_held"
    ACTIVITY_RESUMED = "activity_resumed"
    ACTIVITY_REMOVED = "activity_removed"
    UNEXPECTED_EVENT = "unexpected_event"
    AVAILABLE_TIME_CHANGED = "available_time_changed"
    DAY_MODE_CHANGED = "day_mode_changed"


class LivingActivityStatus(StrEnum):
    """One LivingActivity's own current status, derived by folding its
    own events (P6.1) - HELD is deliberately distinct from POSTPONED:
    HELD means "paused today, expected to resume today" (RESUMED reverses
    it); POSTPONED means "deferred to another day" (P6.3's own "postponed
    work is not incorrectly resurfaced as today's active work" - a
    POSTPONED activity stays out of today's candidates unless the user
    explicitly re-adds or resumes it)."""

    ACTIVE = "active"
    COMPLETED = "completed"
    POSTPONED = "postponed"
    HELD = "held"
    REMOVED = "removed"


class DayInteractionOutcome(StrEnum):
    """What one natural-language statement to the Living Day resolved to
    (P6.4) - a closed vocabulary so a caller never has to guess which
    fields of DayInteractionResult are meaningful. STATUS_QUERY and
    UNRECOGNIZED both carry zero events by construction - a status query
    is read-only (P6.4's own explicit "must not create a new persisted
    state/version when nothing changed"), and an unrecognized statement
    is never guessed into an event (P6.4's own "if a statement is
    ambiguous, do not guess")."""

    EVENTS_RECORDED = "events_recorded"
    CLARIFICATION_NEEDED = "clarification_needed"
    STATUS_QUERY = "status_query"
    UNRECOGNIZED = "unrecognized"
