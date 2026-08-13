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
