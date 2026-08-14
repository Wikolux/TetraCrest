"""LivingDayFlow (P6.2): connects the Living Day State (P6.1) to the
existing Priority Intelligence - "when a meaningful change occurs:
record it, reconstruct current state, recalculate affected priorities,
determine what is now active/suppressed/completed/postponed/newly
relevant, produce recommendations, return them to the user."

Deliberately a thin composition, not a second engine: replan() calls
priority.rank_candidates() directly (the exact same function
priority_flow.py's own build_ranking() calls) and present_replan() calls
PriorityIntelligenceFlow.present() directly - this module owns none of
the actual ranking or narration logic, only the wiring from "a day event
happened" to "here is what the priority engine now says, using the
current living state instead of the static morning DailyIntent."

The OS recommends; it never commands. Nothing in this module writes to
any repository except DayEventRepository.append() - record_event() is
the only method that changes persisted state at all; replan() and
present_replan() are pure reads over whatever has already been recorded,
so recalculating priorities never itself constitutes "the system making
the final decision" (P6.3's own explicit requirement) - it only ever
returns a PriorityRanking/PriorityPresentation for the user to act on or
ignore.
"""

from datetime import date

from app.services.personal_os.candidate_sources import from_living_day_state
from app.services.personal_os.day_mode import DayMode
from app.services.personal_os.daily_intent import DailyIntent
from app.services.personal_os.living_day import DayEvent, LivingDayState, reconstruct
from app.services.personal_os.living_day_interaction import DayInteractionInterpreter, DayInteractionResult, HeuristicDayInteractionInterpreter
from app.services.personal_os.living_day_repository import DayEventRepository
from app.services.personal_os.priority import PriorityRanking, rank_candidates
from app.services.personal_os.priority_flow import PriorityIntelligenceFlow, PriorityPresentation
from app.services.personal_os.repository import DailyIntentRepository
from app.services.personal_os.shared.types import DayInteractionOutcome


class LivingDayFlow:
    def __init__(
        self,
        intent_repository: DailyIntentRepository,
        event_repository: DayEventRepository,
        priority_flow: PriorityIntelligenceFlow,
        interpreter: DayInteractionInterpreter | None = None,
    ) -> None:
        self.intent_repository = intent_repository
        self.event_repository = event_repository
        self.priority_flow = priority_flow
        self.interpreter = interpreter or HeuristicDayInteractionInterpreter()

    def get_state(self, *, organization_id: int, user_id: int, today: date) -> LivingDayState:
        """P6.1: reconstructs the current day purely from persisted
        history - original DailyIntent (if one exists yet; §"all should
        be valid starting states" - a day with no morning intent at all
        is not an error) plus every recorded DayEvent, in order."""
        intent = self._get_intent(organization_id=organization_id, user_id=user_id, today=today)
        events = self.event_repository.list_for_day(organization_id=organization_id, user_id=user_id, day_date=today)
        return reconstruct(intent, events, day_date=today)

    def record_event(self, *, organization_id: int, user_id: int, today: date, event: DayEvent) -> LivingDayState:
        """The only state-changing method in this module - appends one
        real fact and returns the freshly reconstructed state. Never
        silently rewrites the original DailyIntent or any prior event."""
        self.event_repository.append(event, organization_id=organization_id, user_id=user_id, day_date=today)
        return self.get_state(organization_id=organization_id, user_id=user_id, today=today)

    def record_events(self, *, organization_id: int, user_id: int, today: date, events: tuple[DayEvent, ...]) -> LivingDayState:
        """Records several related facts as one call (e.g. an unexpected
        meeting plus the resulting available-time change) - still one
        event per real fact, appended in order, never merged into one
        combined event."""
        for event in events:
            self.event_repository.append(event, organization_id=organization_id, user_id=user_id, day_date=today)
        return self.get_state(organization_id=organization_id, user_id=user_id, today=today)

    def replan(
        self,
        *,
        organization_id: int,
        user_id: int,
        today: date,
        available_hours: float | None = None,
        day_mode: DayMode | None = None,
    ) -> PriorityRanking:
        """P6.2 §1-§5: reconstruct -> recalculate -> recommend. Uses the
        LIVING day's own active activities (from_living_day_state()),
        never the static morning DailyIntent, so a postponed/completed/
        held activity is never re-ranked as if it were still open (P6.3).
        `available_hours`/`day_mode` default to whatever the state itself
        currently records (from AVAILABLE_TIME_CHANGED/DAY_MODE_CHANGED
        events); an explicit override is accepted for a caller that
        wants to ask "what if" without first recording a new event."""
        state = self.get_state(organization_id=organization_id, user_id=user_id, today=today)
        candidates = list(from_living_day_state(state))
        candidates.extend(self.priority_flow.gather_non_intent_candidates(organization_id=organization_id, user_id=user_id))

        resolved_hours = available_hours if available_hours is not None else state.available_hours
        resolved_day_mode = day_mode if day_mode is not None else state.day_mode

        return rank_candidates(tuple(candidates), today=today, available_hours=resolved_hours, day_mode=resolved_day_mode, config=self.priority_flow.config)

    def present_replan(
        self,
        *,
        organization_id: int,
        user_id: int,
        today: date,
        available_hours: float | None = None,
        day_mode: DayMode | None = None,
        conversation_id: int | None = None,
    ) -> PriorityPresentation:
        """replan() plus the one generative rephrasing step, reusing
        PriorityIntelligenceFlow.present() directly - never a second
        narration mechanism."""
        ranking = self.replan(organization_id=organization_id, user_id=user_id, today=today, available_hours=available_hours, day_mode=day_mode)
        return self.priority_flow.present(ranking, organization_id=organization_id, today=today, conversation_id=conversation_id)

    def apply_statement(self, *, organization_id: int, user_id: int, today: date, user_text: str) -> DayInteractionResult:
        """P6.4: the conversational seam - interprets `user_text` against
        the CURRENT state (so target resolution and ambiguity detection
        always see today's real activities, not the morning-only ones),
        and appends events only when the interpreter actually resolved
        some (never for STATUS_QUERY, CLARIFICATION_NEEDED, or
        UNRECOGNIZED - each of those returns zero events by construction,
        so this method's own `if result.events` check is enough to
        guarantee a read-only statement never touches the event log)."""
        state = self.get_state(organization_id=organization_id, user_id=user_id, today=today)
        result = self.interpreter.interpret(user_text, state=state)
        if result.outcome == DayInteractionOutcome.EVENTS_RECORDED and result.events:
            self.record_events(organization_id=organization_id, user_id=user_id, today=today, events=result.events)
        return result

    def _get_intent(self, *, organization_id: int, user_id: int, today: date) -> DailyIntent | None:
        return self.intent_repository.get_for_date(organization_id=organization_id, user_id=user_id, intent_date=today)
