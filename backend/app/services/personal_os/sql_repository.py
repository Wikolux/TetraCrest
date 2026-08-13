"""SqlDailyIntentRepository - the durable DailyIntentRepository
implementation (P2), satisfying the exact same interface
InMemoryDailyIntentRepository already does.

Uses the project's own, already-established repository pattern
(BaseRepository[ModelType] + a domain repository, app/repositories/) and
its own SQLAlchemy model (DailyIntentRecord, app/models/) - not a new
persistence framework, not an ORM alternative, not AgentMemory. This is
the smallest Application-local solution consistent with how every other
piece of structured, tenant-scoped data on this backend is already
stored.

Every save() still inserts a new row, never an UPDATE - the DB-backed
implementation preserves the identical append-only version-history
semantics InMemoryDailyIntentRepository already established; only the
storage medium changed, not the contract or its guarantees.
"""

import json
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.daily_intent_record import DailyIntentRecord
from app.models.evening_reflection_record import EveningReflectionRecord
from app.repositories.daily_intent_record_repository import DailyIntentRecordRepository
from app.repositories.evening_reflection_record_repository import EveningReflectionRecordRepository
from app.services.personal_os.daily_intent import DailyIntent, IntentField, PlannedActivity
from app.services.personal_os.evening import EveningReflection, EveningReflectionRepository
from app.services.personal_os.reconciliation import ReconciliationEvidence, ReconciliationRecord
from app.services.personal_os.repository import DailyIntentRepository
from app.services.personal_os.shared.types import Confidence, DayType, IntentSource, ReconciliationStatus


def _intent_fields_to_json(fields: tuple[IntentField, ...]) -> str:
    return json.dumps([{"value": f.value, "source": f.source.value, "confidence": f.confidence.value} for f in fields])


def _intent_fields_from_json(raw: str) -> tuple[IntentField, ...]:
    return tuple(
        IntentField(value=row["value"], source=IntentSource(row["source"]), confidence=Confidence(row["confidence"]))
        for row in json.loads(raw)
    )


def _activities_to_json(activities: tuple[PlannedActivity, ...]) -> str:
    return json.dumps(
        [
            {"description": a.description, "focus_area": a.focus_area, "deadline": a.deadline.isoformat() if a.deadline else None}
            for a in activities
        ]
    )


def _activities_from_json(raw: str) -> tuple[PlannedActivity, ...]:
    return tuple(
        PlannedActivity(
            description=row["description"],
            focus_area=row["focus_area"],
            deadline=date.fromisoformat(row["deadline"]) if row["deadline"] else None,
        )
        for row in json.loads(raw)
    )


def _strings_to_json(values: tuple[str, ...]) -> str:
    return json.dumps(list(values))


def _strings_from_json(raw: str) -> tuple[str, ...]:
    return tuple(json.loads(raw))


class SqlDailyIntentRepository(DailyIntentRepository):
    def __init__(self, db: Session) -> None:
        self.db = db
        self._records = DailyIntentRecordRepository(db)

    def save(self, intent: DailyIntent, *, organization_id: int, user_id: int) -> DailyIntent:
        record = DailyIntentRecord(
            organization_id=organization_id,
            user_id=user_id,
            intent_date=intent.intent_date,
            stated_intention=intent.stated_intention,
            day_type=intent.day_type.value,
            is_rest_day=intent.is_rest_day,
            continuation_of_date=intent.continuation_of_date,
            supersedes_intent_id=intent.supersedes_intent_id,
            new_priorities_json=_intent_fields_to_json(intent.new_priorities),
            planned_activities_json=_activities_to_json(intent.planned_activities),
            focus_areas_json=_strings_to_json(intent.focus_areas),
            known_constraints_json=_strings_to_json(intent.known_constraints),
            deadlines_json=_strings_to_json(intent.deadlines),
            scheduling_preferences_json=_strings_to_json(intent.scheduling_preferences),
            user_provided_changes_json=_strings_to_json(intent.user_provided_changes),
        )
        self._records.create(record)
        return self._to_domain(record)

    def get_for_date(self, *, organization_id: int, user_id: int, intent_date: date) -> DailyIntent | None:
        record = self._records.get_latest_for_date(organization_id, user_id, intent_date)
        return self._to_domain(record) if record else None

    def get_latest_before(self, *, organization_id: int, user_id: int, before: date) -> DailyIntent | None:
        record = self._records.get_latest_before(organization_id, user_id, before)
        return self._to_domain(record) if record else None

    @staticmethod
    def _to_domain(record: DailyIntentRecord) -> DailyIntent:
        created_at = record.created_at if isinstance(record.created_at, datetime) else datetime.fromisoformat(str(record.created_at))
        updated_at = record.updated_at if isinstance(record.updated_at, datetime) else datetime.fromisoformat(str(record.updated_at))
        return DailyIntent(
            intent_date=record.intent_date,
            stated_intention=record.stated_intention,
            day_type=DayType(record.day_type),
            continuation_of_date=record.continuation_of_date,
            new_priorities=_intent_fields_from_json(record.new_priorities_json),
            planned_activities=_activities_from_json(record.planned_activities_json),
            is_rest_day=record.is_rest_day,
            focus_areas=_strings_from_json(record.focus_areas_json),
            known_constraints=_strings_from_json(record.known_constraints_json),
            deadlines=_strings_from_json(record.deadlines_json),
            scheduling_preferences=_strings_from_json(record.scheduling_preferences_json),
            user_provided_changes=_strings_from_json(record.user_provided_changes_json),
            supersedes_intent_id=record.supersedes_intent_id,
            created_at=created_at,
            updated_at=updated_at,
            intent_id=str(record.id),
        )


def _evidence_to_dict(evidence: ReconciliationEvidence) -> dict:
    return {
        "explicitly_completed": evidence.explicitly_completed,
        "explicitly_postponed": evidence.explicitly_postponed,
        "explicitly_cancelled": evidence.explicitly_cancelled,
        "explicitly_blocked": evidence.explicitly_blocked,
        "explicitly_rested_instead": evidence.explicitly_rested_instead,
        "superseding_priority": evidence.superseding_priority,
        "note": evidence.note,
    }


def _evidence_from_dict(row: dict) -> ReconciliationEvidence:
    return ReconciliationEvidence(
        explicitly_completed=row["explicitly_completed"],
        explicitly_postponed=row["explicitly_postponed"],
        explicitly_cancelled=row["explicitly_cancelled"],
        explicitly_blocked=row["explicitly_blocked"],
        explicitly_rested_instead=row["explicitly_rested_instead"],
        superseding_priority=row["superseding_priority"],
        note=row["note"],
    )


def _reconciliations_to_json(records: tuple[ReconciliationRecord, ...]) -> str:
    return json.dumps(
        [
            {
                "activity_description": record.activity.description,
                "status": record.status.value,
                "evidence": _evidence_to_dict(record.evidence),
            }
            for record in records
        ]
    )


def _reconciliations_from_json(raw: str) -> tuple[ReconciliationRecord, ...]:
    return tuple(
        ReconciliationRecord(
            activity=PlannedActivity(description=row["activity_description"]),
            status=ReconciliationStatus(row["status"]),
            evidence=_evidence_from_dict(row["evidence"]),
        )
        for row in json.loads(raw)
    )


class SqlEveningReflectionRepository(EveningReflectionRepository):
    def __init__(self, db: Session) -> None:
        self.db = db
        self._records = EveningReflectionRecordRepository(db)

    def save(
        self,
        reflection: EveningReflection,
        reconciliations: tuple[ReconciliationRecord, ...],
        *,
        organization_id: int,
        user_id: int,
        daily_intent_id: str | None,
    ) -> EveningReflection:
        record = EveningReflectionRecord(
            organization_id=organization_id,
            user_id=user_id,
            reflection_date=reflection.reflection_date,
            daily_intent_id=int(daily_intent_id) if daily_intent_id else None,
            accomplishments_json=_strings_to_json(reflection.accomplishments),
            unexpected_events_json=_strings_to_json(reflection.unexpected_events),
            lessons_json=_strings_to_json(reflection.lessons),
            decisions_json=_strings_to_json(reflection.decisions),
            worth_remembering_json=_strings_to_json(reflection.worth_remembering),
            preparation_for_tomorrow_json=_strings_to_json(reflection.preparation_for_tomorrow),
            reconciliation_json=_reconciliations_to_json(reconciliations),
        )
        self._records.create(record)
        return reflection

    def get_for_date(self, *, organization_id: int, user_id: int, reflection_date: date) -> EveningReflection | None:
        record = self._records.get_for_date(organization_id, user_id, reflection_date)
        return self._to_domain(record) if record else None

    def get_reconciliations_for_date(
        self, *, organization_id: int, user_id: int, reflection_date: date
    ) -> tuple[ReconciliationRecord, ...]:
        record = self._records.get_for_date(organization_id, user_id, reflection_date)
        return _reconciliations_from_json(record.reconciliation_json) if record else ()

    @staticmethod
    def _to_domain(record: EveningReflectionRecord) -> EveningReflection:
        created_at = (
            record.created_at if isinstance(record.created_at, datetime) else datetime.fromisoformat(str(record.created_at))
        )
        return EveningReflection(
            reflection_date=record.reflection_date,
            accomplishments=_strings_from_json(record.accomplishments_json),
            unexpected_events=_strings_from_json(record.unexpected_events_json),
            lessons=_strings_from_json(record.lessons_json),
            decisions=_strings_from_json(record.decisions_json),
            worth_remembering=_strings_from_json(record.worth_remembering_json),
            preparation_for_tomorrow=_strings_from_json(record.preparation_for_tomorrow_json),
            created_at=created_at,
        )
