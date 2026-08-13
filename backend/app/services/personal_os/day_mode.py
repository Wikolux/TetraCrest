"""DayMode (P5 §11-§12): "what kind of day are we having?" - asked
before a full priority ranking is generated, distinct from DayType
(daily_intent.py).

DayType classifies WHAT WAS PLANNED (work/study/project/mixed/rest/
other) and is set by MorningInteractionFlow from the user's own stated
intention for today's activities. DayMode is a separate, earlier signal:
the user's own stated POSTURE for the day (structured, flexible,
recovery, family-focused...) that the Priority Engine uses to weight
candidates BEFORE any activities are even planned - a FAMILY_FOCUSED day
and a REST DayType can coexist, but so can a FAMILY_FOCUSED day where the
user still plans real work later ("I want family time this morning, then
a focused afternoon"). Conflating the two would force one enum to answer
two genuinely different questions; keeping them separate lets a future
integration set DayType without ever needing to also fabricate a DayMode,
and vice versa.

infer_day_mode() mirrors morning_flow.py's own _infer_day_type() heuristic
discipline exactly: a small, honestly-labeled keyword match, returning
None (never a guessed default) when nothing matches, so a caller is never
tempted to treat a heuristic miss as a real user statement."""

from dataclasses import dataclass

from app.services.personal_os.shared.types import DayModeKind, LifeDomain

_DAY_MODE_KEYWORDS: tuple[tuple[DayModeKind, tuple[str, ...]], ...] = (
    (DayModeKind.RECOVERY, ("recover", "recovery", "rest day", "day off", "take it easy")),
    (DayModeKind.FAMILY_FOCUSED, ("family", "family day", "with my wife", "with my husband", "with the kids")),
    (DayModeKind.STUDY_FOCUSED, ("study day", "learning day", "focus on studying")),
    (DayModeKind.PROJECT_FOCUSED, ("project day", "build day", "shipping day")),
    (DayModeKind.STRUCTURED_PRODUCTIVE, ("productive", "focused workday", "structured day", "get a lot done")),
    (DayModeKind.FLEXIBLE, ("flexible", "see how it goes", "play it by ear")),
)

# Which domains a given day mode boosts (§12's own worked examples:
# PROJECT_FOCUSED raises project-related priorities; STUDY_FOCUSED raises
# learning priorities) - a small, named, inspectable table rather than
# per-mode branching logic scattered through the priority engine.
DAY_MODE_DOMAIN_BOOST: dict[DayModeKind, tuple[LifeDomain, ...]] = {
    DayModeKind.PROJECT_FOCUSED: (LifeDomain.TECHNICAL_PROJECTS, LifeDomain.BUSINESS),
    DayModeKind.STUDY_FOCUSED: (LifeDomain.STUDY,),
    DayModeKind.FAMILY_FOCUSED: (LifeDomain.FAMILY,),
}

# Day modes where work-domain candidates should NOT be aggressively
# pushed (§12: FAMILY_FOCUSED should not aggressively push work;
# RECOVERY should reduce optional workload) - influences ranking only,
# never deletes or hides a candidate outright (§12's own "does not
# permanently change the user's life priorities").
DAY_MODE_SUPPRESSES_WORK: frozenset[DayModeKind] = frozenset({DayModeKind.FAMILY_FOCUSED, DayModeKind.RECOVERY})

# Day modes that reduce how many optional items are worth surfacing at
# all (§12: "RECOVERY - the system should reduce optional workload").
DAY_MODE_REDUCES_OPTIONAL: frozenset[DayModeKind] = frozenset({DayModeKind.RECOVERY, DayModeKind.FAMILY_FOCUSED})


@dataclass(frozen=True)
class DayMode:
    """The user's own stated posture for today - kind is one of the
    named DayModeKind values, or CUSTOM with the user's own label
    preserved verbatim (§11's own "allow a user-defined day mode"),
    never coerced into the nearest named kind."""

    kind: DayModeKind
    custom_label: str = ""
    stated_by_user: bool = True

    def __post_init__(self) -> None:
        if self.kind == DayModeKind.CUSTOM and not self.custom_label:
            raise ValueError("DayMode.custom_label is required when kind is CUSTOM")
        if self.kind != DayModeKind.CUSTOM and self.custom_label:
            raise ValueError("DayMode.custom_label is only meaningful when kind is CUSTOM")

    @property
    def label(self) -> str:
        return self.custom_label if self.kind == DayModeKind.CUSTOM else self.kind.value.replace("_", " ")


def infer_day_mode(user_text: str) -> DayMode | None:
    """A heuristic keyword match only (honestly labeled, same discipline
    as morning_flow.py's own _infer_day_type) - returns None, never a
    guessed default, when nothing matches. Never presented to a caller as
    real natural-language understanding."""
    if not user_text:
        return None
    lowered = user_text.lower()
    for kind, keywords in _DAY_MODE_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return DayMode(kind=kind, stated_by_user=True)
    return None
