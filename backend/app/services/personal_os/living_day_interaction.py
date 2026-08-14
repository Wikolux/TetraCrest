"""Conversational interaction seam (P6.4): a replaceable layer
translating natural user statements into Living Day operations (P6.1).

DayInteractionInterpreter is the seam itself - an ABC with exactly one
method, `interpret()`. HeuristicDayInteractionInterpreter is the one
concrete implementation this milestone builds: an honestly-labeled
keyword heuristic, matching morning_flow.py's/evening_flow.py's/
day_mode.py's own established discipline exactly (no LLM provider is
registered anywhere on this platform; every field this interpreter
extracts is a plain keyword/substring match, never claimed as real NLU).
A future, smarter interpreter (real structured NLU, an LLM-backed
classifier reusing RuntimeAdapter/PromptBuilder) satisfies this exact
same interface without living_day_flow.py or anything downstream of it
changing at all - that is what "replaceable" means here.

Two hard rules, enforced structurally, not just by convention:
- A STATUS_QUERY never carries events (DayInteractionResult.events is
  always empty for it) - living_day_flow.py's own apply_statement() only
  calls record_events() when outcome == EVENTS_RECORDED, so asking "what's
  the plan?" can never append to the event log.
- Ambiguous targets are never guessed. `_matching_activities()` returning
  more than one match always produces CLARIFICATION_NEEDED, never an
  arbitrary pick of "the first match."
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import uuid4

from app.services.personal_os.day_mode import infer_day_mode
from app.services.personal_os.living_day import DayEvent, LivingActivity, LivingDayState
from app.services.personal_os.shared.types import DayEventType, DayInteractionOutcome

_STATUS_QUERY_MARKERS = (
    "what's the plan", "what is the plan", "whats the plan", "what's on today",
    "what's left", "show me the plan", "what do i have today", "what is my status",
    "status update", "what's my day look like",
)
_HOLD_ALL_MARKERS = ("hold everything", "hold all", "pause everything", "pause all")
_RESUME_ALL_MARKERS = ("resume everything", "resume all", "resume the things i paused", "unpause everything", "resume what i paused")
_UNEXPECTED_EVENT_MARKERS = ("meeting", "unexpected", "emergency", "appointment", "interruption", "came up", "call came in")
_ADD_MARKERS = ("add ", "i want to add", "also need to", "put on my list", "i need to also")
_COMPLETE_MARKERS = ("i'm done with", "i am done with", "done with", "just finished", "finished", "completed", "wrapped up")
_POSTPONE_MARKERS = ("postpone", "push back", "not doing today", "move to another day", "move to tomorrow")
_HOLD_MARKERS = ("hold ",)
_RESUME_MARKERS = ("resume ",)
_REMOVE_MARKERS = ("remove", "cancel", "never mind", "forget about", "drop ")

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_STEM_LENGTH = 5


@dataclass(frozen=True)
class DayInteractionResult:
    """What one statement resolved to - a single flat, inspectable
    result (never several parallel result classes), matching the same
    "minimum model necessary" discipline every other Personal OS result
    type already follows."""

    outcome: DayInteractionOutcome
    events: tuple[DayEvent, ...] = field(default_factory=tuple)
    clarification_question: str = ""
    candidates: tuple[LivingActivity, ...] = field(default_factory=tuple)
    message: str = ""


class DayInteractionInterpreter(ABC):
    @abstractmethod
    def interpret(self, user_text: str, *, state: LivingDayState) -> DayInteractionResult:
        raise NotImplementedError


def _significant_words(text: str) -> list[str]:
    """len > 3, matching evening_flow.py's own _mentions() threshold
    exactly - short filler words ("for", "the", "and", "my") are common
    enough across unrelated activity descriptions that including them
    would produce false-positive ambiguity (e.g. "Postpone applying for
    jobs" nearly matched an unrelated errand purely because both
    descriptions happened to contain "for")."""
    return [w for w in re.sub(r"[^\w\s]", " ", text.lower()).split() if len(w) > 3]


def _stem(word: str) -> str:
    return word[:_STEM_LENGTH]


def _matching_activities(target_text: str, pool: tuple[LivingActivity, ...]) -> tuple[LivingActivity, ...]:
    """Word-stem overlap matching, mirroring evening_flow.py's own
    _mentions() heuristic exactly (an honest keyword match, never real
    NLU) - a candidate matches if it shares at least one significant
    word-stem with the target text, so "studying" matches "Study system
    design" and "Call John" matches both "Call John about the proposal"
    and "Call John re: the invoice" (correctly, since that ambiguity is
    exactly what should trigger a clarification request)."""
    target_stems = {_stem(w) for w in _significant_words(target_text)}
    if not target_stems:
        return ()
    matches = []
    for activity in pool:
        description_stems = {_stem(w) for w in _significant_words(activity.description)}
        if target_stems & description_stems:
            matches.append(activity)
    return tuple(matches)


def _strip_marker(text: str, markers: tuple[str, ...]) -> str:
    lowered = text.lower()
    for marker in markers:
        idx = lowered.find(marker)
        if idx != -1:
            return text[idx + len(marker) :].strip(" .;:!?").strip()
    return text.strip(" .;:!?")


def _parse_duration_hours(text: str) -> float | None:
    """An honest heuristic only (never claimed as real NLU) - a plain
    digit-plus-unit match, or a small closed number-word table. Returns
    None, never a guessed default, when no duration is stated."""
    lowered = text.lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)", lowered)
    if match:
        return float(match.group(1))
    if re.search(r"half\s*(?:an\s*)?hour", lowered):
        return 0.5
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b\s*(?:hours?|hrs?)", lowered):
            return float(value)
    return None


class HeuristicDayInteractionInterpreter(DayInteractionInterpreter):
    """The one concrete interpreter this milestone builds - see module
    docstring for the honesty/replaceability discipline it follows."""

    def interpret(self, user_text: str, *, state: LivingDayState) -> DayInteractionResult:
        if not user_text or not user_text.strip():
            return DayInteractionResult(outcome=DayInteractionOutcome.UNRECOGNIZED, message="I didn't catch anything to act on.")

        lowered = user_text.lower()

        if any(marker in lowered for marker in _STATUS_QUERY_MARKERS):
            return DayInteractionResult(outcome=DayInteractionOutcome.STATUS_QUERY)

        if any(marker in lowered for marker in _HOLD_ALL_MARKERS):
            return self._hold_all(user_text, state)

        if any(marker in lowered for marker in _RESUME_ALL_MARKERS):
            events = tuple(
                DayEvent(event_type=DayEventType.ACTIVITY_RESUMED, activity_id=a.activity_id, reason=user_text) for a in state.held_activities
            )
            return DayInteractionResult(outcome=DayInteractionOutcome.EVENTS_RECORDED, events=events)

        if any(marker in lowered for marker in _UNEXPECTED_EVENT_MARKERS):
            return self._unexpected_event(user_text, state)

        if any(marker in lowered for marker in _ADD_MARKERS):
            return self._add_activity(user_text)

        for markers, event_type, pool in (
            (_COMPLETE_MARKERS, DayEventType.ACTIVITY_COMPLETED, state.active_activities),
            (_POSTPONE_MARKERS, DayEventType.ACTIVITY_POSTPONED, state.active_activities),
            (_HOLD_MARKERS, DayEventType.ACTIVITY_HELD, state.active_activities),
            (_RESUME_MARKERS, DayEventType.ACTIVITY_RESUMED, state.held_activities),
            (_REMOVE_MARKERS, DayEventType.ACTIVITY_REMOVED, state.active_activities),
        ):
            marker = next((m for m in markers if m in lowered), None)
            if marker is None:
                continue
            return self._resolve_target(user_text, marker, event_type, pool)

        return DayInteractionResult(
            outcome=DayInteractionOutcome.UNRECOGNIZED, message="I'm not sure what you'd like me to do with that - could you rephrase it?"
        )

    @staticmethod
    def _hold_all(user_text: str, state: LivingDayState) -> DayInteractionResult:
        events = [DayEvent(event_type=DayEventType.ACTIVITY_HELD, activity_id=a.activity_id, reason=user_text) for a in state.active_activities]
        day_mode = infer_day_mode(user_text)
        if day_mode is not None:
            events.append(DayEvent(event_type=DayEventType.DAY_MODE_CHANGED, day_mode=day_mode))
        return DayInteractionResult(outcome=DayInteractionOutcome.EVENTS_RECORDED, events=tuple(events))

    @staticmethod
    def _unexpected_event(user_text: str, state: LivingDayState) -> DayInteractionResult:
        duration = _parse_duration_hours(user_text)
        activity_id = str(uuid4())
        events = [
            DayEvent(event_type=DayEventType.UNEXPECTED_EVENT, activity_id=activity_id, description=user_text.strip().rstrip("."), estimated_hours=duration)
        ]
        if duration is not None:
            new_available_hours = max(0.0, state.available_hours - duration)
            events.append(DayEvent(event_type=DayEventType.AVAILABLE_TIME_CHANGED, available_hours=new_available_hours))
        return DayInteractionResult(outcome=DayInteractionOutcome.EVENTS_RECORDED, events=tuple(events))

    @staticmethod
    def _add_activity(user_text: str) -> DayInteractionResult:
        description = _strip_marker(user_text, _ADD_MARKERS)
        if not description:
            return DayInteractionResult(outcome=DayInteractionOutcome.UNRECOGNIZED, message="What would you like to add?")
        activity_id = str(uuid4())
        return DayInteractionResult(
            outcome=DayInteractionOutcome.EVENTS_RECORDED,
            events=(DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id=activity_id, description=description),),
        )

    @staticmethod
    def _resolve_target(
        user_text: str, marker: str, event_type: DayEventType, pool: tuple[LivingActivity, ...]
    ) -> DayInteractionResult:
        target_text = _strip_marker(user_text, (marker,))
        matches = _matching_activities(target_text, pool)

        if len(matches) == 0:
            return DayInteractionResult(
                outcome=DayInteractionOutcome.UNRECOGNIZED, message=f'I could not find anything matching "{target_text}" to act on.'
            )
        if len(matches) > 1:
            names = "; ".join(f'"{a.description}"' for a in matches)
            return DayInteractionResult(
                outcome=DayInteractionOutcome.CLARIFICATION_NEEDED,
                clarification_question=f"There are a few things that could match - which one did you mean: {names}?",
                candidates=matches,
            )
        return DayInteractionResult(
            outcome=DayInteractionOutcome.EVENTS_RECORDED,
            events=(DayEvent(event_type=event_type, activity_id=matches[0].activity_id, reason=user_text),),
        )
