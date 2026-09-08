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

from app.models.adaptation_record import AdaptationRecord
from app.models.daily_intent_record import DailyIntentRecord
from app.models.day_event_record import DayEventRecord
from app.models.evening_reflection_record import EveningReflectionRecord
from app.models.experiment_record import ExperimentRecord
from app.models.life_domain_state_record import LifeDomainStateRecord
from app.models.mission_record import MissionRecord
from app.models.pattern_record import PatternRecord
from app.repositories.adaptation_record_repository import AdaptationRecordRepository
from app.repositories.daily_intent_record_repository import DailyIntentRecordRepository
from app.repositories.day_event_record_repository import DayEventRecordRepository
from app.repositories.evening_reflection_record_repository import EveningReflectionRecordRepository
from app.repositories.experiment_record_repository import ExperimentRecordRepository
from app.repositories.life_domain_state_record_repository import LifeDomainStateRecordRepository
from app.repositories.mission_record_repository import MissionRecordRepository
from app.repositories.pattern_record_repository import PatternRecordRepository
from app.services.personal_os.adaptation import Adaptation, AdaptationEffect, AdaptationTarget
from app.services.personal_os.adaptation_repository import ACTIVE_ADAPTATION_STATUSES, AdaptationRepository
from app.services.personal_os.daily_intent import DailyIntent, IntentField, PlannedActivity
from app.services.personal_os.day_mode import DayMode
from app.services.personal_os.evening import EveningReflection, EveningReflectionRepository
from app.services.personal_os.experiment import Experiment, ExperimentBaseline, ExperimentComparison, ExperimentMeasurement
from app.services.personal_os.experiment_repository import ACTIVE_EXPERIMENT_STATUSES, ExperimentRepository
from app.services.personal_os.life_domain import LifeDomainState
from app.services.personal_os.life_domain_repository import LifeDomainStateRepository
from app.services.personal_os.living_day import DayEvent
from app.services.personal_os.living_day_repository import DayEventRepository
from app.services.personal_os.mission import AutonomyGrant, Mission
from app.services.personal_os.mission_repository import ACTIVE_MISSION_STATUSES, MissionRepository
from app.services.personal_os.pattern import Pattern, PatternEvidenceItem
from app.services.personal_os.pattern_repository import PatternRepository
from app.services.personal_os.reasoning import GrowthRecommendation, Hypothesis, InferredPattern, ObservedFact
from app.services.personal_os.reconciliation import ReconciliationEvidence, ReconciliationRecord
from app.services.personal_os.repository import DailyIntentRepository
from app.services.personal_os.shared.types import (
    AdaptationEffectKind,
    AdaptationScope,
    AdaptationStatus,
    AutonomyAction,
    Confidence,
    DayEventType,
    DayModeKind,
    DayType,
    ExperimentOutcome,
    ExperimentStatus,
    ExperimentUserDecision,
    IntentSource,
    LifeDomain,
    LifeDomainClassification,
    LifeDomainStatus,
    MissionStatus,
    PatternStatus,
    PatternType,
    PriorityDirection,
    ReconciliationStatus,
)


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
            {
                "description": a.description,
                "focus_area": a.focus_area,
                "deadline": a.deadline.isoformat() if a.deadline else None,
                "estimated_hours": a.estimated_hours,
            }
            for a in activities
        ]
    )


def _activities_from_json(raw: str) -> tuple[PlannedActivity, ...]:
    return tuple(
        PlannedActivity(
            description=row["description"],
            focus_area=row["focus_area"],
            deadline=date.fromisoformat(row["deadline"]) if row["deadline"] else None,
            # .get() - rows written before P3 have no estimated_hours key at all.
            estimated_hours=row.get("estimated_hours"),
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

    def list_range(self, *, organization_id: int, user_id: int, start: date, end: date) -> tuple[DailyIntent, ...]:
        all_versions = self._records.list_by_date_range(organization_id, user_id, start, end)
        latest_by_date: dict[date, DailyIntentRecord] = {}
        for record in all_versions:  # ascending id order - later versions overwrite earlier ones per date
            latest_by_date[record.intent_date] = record
        return tuple(self._to_domain(latest_by_date[d]) for d in sorted(latest_by_date))

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
        "actual_hours": evidence.actual_hours,
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
        # .get() - rows written before P3 have no actual_hours key at all.
        actual_hours=row.get("actual_hours"),
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

    def list_reconciliations_range(
        self, *, organization_id: int, user_id: int, start: date, end: date
    ) -> tuple[tuple[date, ReconciliationRecord], ...]:
        records = self._records.list_by_date_range(organization_id, user_id, start, end)
        pairs = []
        for record in records:
            for reconciliation in _reconciliations_from_json(record.reconciliation_json):
                pairs.append((record.reflection_date, reconciliation))
        return tuple(pairs)

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


# --- Pattern (P3) serialization -------------------------------------------------------------


def _evidence_items_to_json(items: tuple[PatternEvidenceItem, ...]) -> str:
    return json.dumps(
        [
            {
                "observation_date": item.observation_date.isoformat(),
                "activity_description": item.activity_description,
                "activity_category": item.activity_category,
                "status": item.status,
                "estimated_hours": item.estimated_hours,
                "actual_hours": item.actual_hours,
                "stated_reason": item.stated_reason,
            }
            for item in items
        ]
    )


def _evidence_items_from_json(raw: str) -> tuple[PatternEvidenceItem, ...]:
    return tuple(
        PatternEvidenceItem(
            observation_date=date.fromisoformat(row["observation_date"]),
            activity_description=row["activity_description"],
            activity_category=row["activity_category"],
            status=row["status"],
            estimated_hours=row.get("estimated_hours"),
            actual_hours=row.get("actual_hours"),
            stated_reason=row.get("stated_reason", ""),
        )
        for row in json.loads(raw)
    )


def _facts_to_dicts(facts: tuple[ObservedFact, ...]) -> list[dict]:
    return [{"statement": f.statement, "evidence_ref": f.evidence_ref} for f in facts]


def _facts_from_dicts(rows: list[dict]) -> tuple[ObservedFact, ...]:
    return tuple(ObservedFact(statement=row["statement"], evidence_ref=row.get("evidence_ref", "")) for row in rows)


def _hypothesis_to_dict(hypothesis: Hypothesis) -> dict:
    return {
        "statement": hypothesis.statement,
        "explains_statement": hypothesis.explains.statement,
        "explains_supporting_facts": _facts_to_dicts(hypothesis.explains.supporting_facts),
        "informed_by": [{"statement": e.statement, "explains_activity": e.explains_activity} for e in hypothesis.informed_by],
    }


def _hypothesis_from_dict(row: dict) -> Hypothesis:
    from app.services.personal_os.reasoning import UserExplanation

    pattern = InferredPattern(statement=row["explains_statement"], supporting_facts=_facts_from_dicts(row["explains_supporting_facts"]))
    explanations = tuple(
        UserExplanation(statement=e["statement"], explains_activity=e.get("explains_activity", "")) for e in row.get("informed_by", [])
    )
    return Hypothesis(statement=row["statement"], explains=pattern, informed_by=explanations)


def _hypotheses_to_json(hypotheses: tuple[Hypothesis, ...]) -> str:
    return json.dumps([_hypothesis_to_dict(h) for h in hypotheses])


def _hypotheses_from_json(raw: str) -> tuple[Hypothesis, ...]:
    return tuple(_hypothesis_from_dict(row) for row in json.loads(raw))


def _recommendation_to_json(recommendation: GrowthRecommendation | None) -> str | None:
    if recommendation is None:
        return None
    return json.dumps({"statement": recommendation.statement, "responds_to": _hypothesis_to_dict(recommendation.responds_to)})


def _recommendation_from_json(raw: str | None) -> GrowthRecommendation | None:
    if raw is None:
        return None
    row = json.loads(raw)
    return GrowthRecommendation(statement=row["statement"], responds_to=_hypothesis_from_dict(row["responds_to"]))


class SqlPatternRepository(PatternRepository):
    def __init__(self, db: Session) -> None:
        self.db = db
        self._records = PatternRecordRepository(db)

    def save(self, pattern: Pattern, *, organization_id: int, user_id: int) -> Pattern:
        record = PatternRecord(
            organization_id=organization_id,
            user_id=user_id,
            pattern_type=pattern.pattern_type.value,
            observation_window_start=pattern.observation_window_start,
            observation_window_end=pattern.observation_window_end,
            evidence_json=_evidence_items_to_json(pattern.evidence),
            observed_facts_json=json.dumps(_facts_to_dicts(pattern.observed_facts)),
            pattern_statement=pattern.pattern_statement,
            confidence=pattern.confidence.value,
            possible_hypotheses_json=_hypotheses_to_json(pattern.possible_hypotheses),
            user_interpretation=pattern.user_interpretation,
            recommendation_json=_recommendation_to_json(pattern.recommendation),
            status=pattern.status.value,
            supersedes_pattern_id=pattern.supersedes_pattern_id,
        )
        self._records.create(record)
        return self._to_domain(record)

    def get_latest(self, *, organization_id: int, user_id: int, pattern_type: PatternType) -> Pattern | None:
        record = self._records.get_latest_by_type(organization_id, user_id, pattern_type.value)
        return self._to_domain(record) if record else None

    def list_active(self, *, organization_id: int, user_id: int) -> tuple[Pattern, ...]:
        records = self._records.list_latest_per_type(organization_id, user_id)
        patterns = [self._to_domain(record) for record in records]
        active = [p for p in patterns if p.status not in (PatternStatus.DISMISSED, PatternStatus.SUPERSEDED)]
        return tuple(sorted(active, key=lambda p: p.created_at))

    @staticmethod
    def _to_domain(record: PatternRecord) -> Pattern:
        created_at = record.created_at if isinstance(record.created_at, datetime) else datetime.fromisoformat(str(record.created_at))
        updated_at = record.updated_at if isinstance(record.updated_at, datetime) else datetime.fromisoformat(str(record.updated_at))
        return Pattern(
            pattern_id=str(record.id),
            pattern_type=PatternType(record.pattern_type),
            observation_window_start=record.observation_window_start,
            observation_window_end=record.observation_window_end,
            evidence=_evidence_items_from_json(record.evidence_json),
            observed_facts=_facts_from_dicts(json.loads(record.observed_facts_json)),
            pattern_statement=record.pattern_statement,
            confidence=Confidence(record.confidence),
            possible_hypotheses=_hypotheses_from_json(record.possible_hypotheses_json),
            user_interpretation=record.user_interpretation,
            recommendation=_recommendation_from_json(record.recommendation_json),
            status=PatternStatus(record.status),
            supersedes_pattern_id=record.supersedes_pattern_id,
            created_at=created_at,
            updated_at=updated_at,
        )


# --- Experiment (P4) --------------------------------------------------------------------------


def _baseline_to_dict(baseline: ExperimentBaseline) -> dict:
    return {
        "metric": baseline.metric,
        "category": baseline.category,
        "period_start": baseline.period_start.isoformat(),
        "period_end": baseline.period_end.isoformat(),
        "value": baseline.value,
        "observation_count": baseline.observation_count,
    }


def _baseline_from_dict(row: dict) -> ExperimentBaseline:
    return ExperimentBaseline(
        metric=row["metric"],
        category=row["category"],
        period_start=date.fromisoformat(row["period_start"]),
        period_end=date.fromisoformat(row["period_end"]),
        value=row["value"],
        observation_count=row["observation_count"],
    )


def _measurement_to_dict(measurement: ExperimentMeasurement) -> dict:
    return {
        "metric": measurement.metric,
        "category": measurement.category,
        "period_start": measurement.period_start.isoformat(),
        "period_end": measurement.period_end.isoformat(),
        "value": measurement.value,
        "observation_count": measurement.observation_count,
    }


def _measurement_from_dict(row: dict) -> ExperimentMeasurement:
    return ExperimentMeasurement(
        metric=row["metric"],
        category=row["category"],
        period_start=date.fromisoformat(row["period_start"]),
        period_end=date.fromisoformat(row["period_end"]),
        value=row["value"],
        observation_count=row["observation_count"],
    )


def _comparison_to_json(comparison: ExperimentComparison | None) -> str | None:
    if comparison is None:
        return None
    return json.dumps(
        {
            "baseline": _baseline_to_dict(comparison.baseline),
            "measurement": _measurement_to_dict(comparison.measurement),
            "absolute_change": comparison.absolute_change,
            "relative_change": comparison.relative_change,
            "outcome": comparison.outcome.value,
            "confidence": comparison.confidence.value,
            "observation_statement": comparison.observation_statement,
        }
    )


def _comparison_from_json(raw: str | None) -> ExperimentComparison | None:
    if raw is None:
        return None
    row = json.loads(raw)
    return ExperimentComparison(
        baseline=_baseline_from_dict(row["baseline"]),
        measurement=_measurement_from_dict(row["measurement"]),
        absolute_change=row["absolute_change"],
        relative_change=row.get("relative_change"),
        outcome=ExperimentOutcome(row["outcome"]),
        confidence=Confidence(row["confidence"]),
        observation_statement=row["observation_statement"],
    )


class SqlExperimentRepository(ExperimentRepository):
    """Mirrors SqlPatternRepository's own shape, with one deliberate
    difference: Pattern's SQL backend derives `pattern_id` from the row's
    own auto-increment id (there is only ever one active Pattern per
    type, so "latest row of this type" is enough); an Experiment has no
    such small, fixed grouping key - a user may have many concurrent or
    historical experiments - so `experiment_id` here is a real, stable
    value (generated once, at the first save) stored in its own indexed
    column and reused across every later lifecycle version, exactly the
    identity InMemoryExperimentRepository already assigns via its own
    counter."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._records = ExperimentRecordRepository(db)

    def save(self, experiment: Experiment, *, organization_id: int, user_id: int) -> Experiment:
        from uuid import uuid4

        experiment_id = experiment.experiment_id or str(uuid4())
        record = ExperimentRecord(
            organization_id=organization_id,
            user_id=user_id,
            experiment_id=experiment_id,
            pattern_id=experiment.pattern_id,
            hypothesis_statement=experiment.hypothesis_statement,
            adjustment=experiment.adjustment,
            measurement_plan=experiment.measurement_plan,
            baseline_json=json.dumps(_baseline_to_dict(experiment.baseline)),
            started_on=experiment.started_on,
            review_date=experiment.review_date,
            status=experiment.status.value,
            comparison_json=_comparison_to_json(experiment.comparison),
            review_narrative=experiment.review_narrative,
            decision=experiment.decision.value if experiment.decision else None,
            decision_reason=experiment.decision_reason,
            review_outcome=experiment.review_outcome,
        )
        self._records.create(record)
        return self._to_domain(record)

    def get_latest(self, *, organization_id: int, user_id: int, experiment_id: str) -> Experiment | None:
        record = self._records.get_latest_by_experiment_id(organization_id, user_id, experiment_id)
        return self._to_domain(record) if record else None

    def get_history(self, *, organization_id: int, user_id: int, experiment_id: str) -> tuple[Experiment, ...]:
        records = self._records.list_history(organization_id, user_id, experiment_id)
        return tuple(self._to_domain(record) for record in records)

    def list_active(self, *, organization_id: int, user_id: int) -> tuple[Experiment, ...]:
        records = self._records.list_latest_per_experiment(organization_id, user_id)
        experiments = [self._to_domain(record) for record in records]
        active = [e for e in experiments if e.status in ACTIVE_EXPERIMENT_STATUSES]
        return tuple(sorted(active, key=lambda e: e.created_at))

    def list_ready_for_review(self, *, organization_id: int, user_id: int, today) -> tuple[Experiment, ...]:
        ready = []
        for experiment in self.list_active(organization_id=organization_id, user_id=user_id):
            if experiment.status == ExperimentStatus.READY_FOR_REVIEW:
                ready.append(experiment)
            elif experiment.status == ExperimentStatus.ACTIVE and experiment.review_date is not None and experiment.review_date <= today:
                ready.append(experiment)
        return tuple(sorted(ready, key=lambda e: e.review_date or e.created_at.date()))

    @staticmethod
    def _to_domain(record: ExperimentRecord) -> Experiment:
        created_at = record.created_at if isinstance(record.created_at, datetime) else datetime.fromisoformat(str(record.created_at))
        updated_at = record.updated_at if isinstance(record.updated_at, datetime) else datetime.fromisoformat(str(record.updated_at))
        return Experiment(
            experiment_id=record.experiment_id,
            pattern_id=record.pattern_id,
            hypothesis_statement=record.hypothesis_statement,
            adjustment=record.adjustment,
            measurement_plan=record.measurement_plan,
            baseline=_baseline_from_dict(json.loads(record.baseline_json)),
            started_on=record.started_on,
            review_date=record.review_date,
            status=ExperimentStatus(record.status),
            comparison=_comparison_from_json(record.comparison_json),
            review_narrative=record.review_narrative,
            decision=ExperimentUserDecision(record.decision) if record.decision else None,
            decision_reason=record.decision_reason,
            review_outcome=record.review_outcome,
            created_at=created_at,
            updated_at=updated_at,
        )


# --- LifeDomainState (P5) ---------------------------------------------------------------------


class SqlLifeDomainStateRepository(LifeDomainStateRepository):
    """Mirrors SqlPatternRepository's own shape exactly - LifeDomainState
    is keyed by LifeDomain the same way Pattern is keyed by PatternType
    (one current state per domain), so state_id is likewise derived from
    the row's own auto-increment id."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._records = LifeDomainStateRecordRepository(db)

    def save(self, state: LifeDomainState, *, organization_id: int, user_id: int) -> LifeDomainState:
        record = LifeDomainStateRecord(
            organization_id=organization_id,
            user_id=user_id,
            domain=state.domain.value,
            status=state.status.value,
            classification=state.classification.value,
            objective=state.objective,
            focus=state.focus,
            context_notes=state.context_notes,
            constraints_json=json.dumps(list(state.constraints)),
            deadlines_json=json.dumps(list(state.deadlines)),
            related_mission_ids_json=json.dumps(list(state.related_mission_ids)),
            last_reviewed_at=state.last_reviewed_at,
            supersedes_state_id=state.supersedes_state_id,
        )
        self._records.create(record)
        return self._to_domain(record)

    def get_latest(self, *, organization_id: int, user_id: int, domain: LifeDomain) -> LifeDomainState | None:
        record = self._records.get_latest_by_domain(organization_id, user_id, domain.value)
        return self._to_domain(record) if record else None

    def get_history(self, *, organization_id: int, user_id: int, domain: LifeDomain) -> tuple[LifeDomainState, ...]:
        records = self._records.list_history(organization_id, user_id, domain.value)
        return tuple(self._to_domain(record) for record in records)

    def list_all_latest(self, *, organization_id: int, user_id: int) -> tuple[LifeDomainState, ...]:
        records = self._records.list_latest_per_domain(organization_id, user_id)
        states = [self._to_domain(record) for record in records]
        return tuple(sorted(states, key=lambda s: s.domain.value))

    @staticmethod
    def _to_domain(record: LifeDomainStateRecord) -> LifeDomainState:
        last_reviewed_at = record.last_reviewed_at if isinstance(record.last_reviewed_at, datetime) else datetime.fromisoformat(str(record.last_reviewed_at))
        created_at = record.created_at if isinstance(record.created_at, datetime) else datetime.fromisoformat(str(record.created_at))
        updated_at = record.updated_at if isinstance(record.updated_at, datetime) else datetime.fromisoformat(str(record.updated_at))
        return LifeDomainState(
            domain=LifeDomain(record.domain),
            status=LifeDomainStatus(record.status),
            classification=LifeDomainClassification(record.classification),
            objective=record.objective,
            focus=record.focus,
            context_notes=record.context_notes,
            constraints=tuple(json.loads(record.constraints_json)),
            deadlines=tuple(json.loads(record.deadlines_json)),
            related_mission_ids=tuple(json.loads(record.related_mission_ids_json)),
            last_reviewed_at=last_reviewed_at,
            supersedes_state_id=record.supersedes_state_id,
            created_at=created_at,
            updated_at=updated_at,
            state_id=str(record.id),
        )


# --- Mission (P5) --------------------------------------------------------------------------------


def _autonomy_grant_to_dict(grant: AutonomyGrant) -> dict:
    return {
        "action": grant.action.value,
        "scope": grant.scope,
        "granted_at": grant.granted_at.isoformat(),
        "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
        "conditions": list(grant.conditions),
        "revoked": grant.revoked,
        "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
    }


def _autonomy_grant_from_dict(row: dict) -> AutonomyGrant:
    return AutonomyGrant(
        action=AutonomyAction(row["action"]),
        scope=row["scope"],
        granted_at=datetime.fromisoformat(row["granted_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]) if row.get("expires_at") else None,
        conditions=tuple(row.get("conditions", [])),
        revoked=row.get("revoked", False),
        revoked_at=datetime.fromisoformat(row["revoked_at"]) if row.get("revoked_at") else None,
    )


class SqlMissionRepository(MissionRepository):
    """Mirrors SqlExperimentRepository's own shape exactly - a real,
    stable mission_id (generated once, at the first save) stored in its
    own indexed column and reused across every later lifecycle version,
    since a user may have many concurrent or historical missions."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._records = MissionRecordRepository(db)

    def save(self, mission: Mission, *, organization_id: int, user_id: int) -> Mission:
        from uuid import uuid4

        mission_id = mission.mission_id or str(uuid4())
        record = MissionRecord(
            organization_id=organization_id,
            user_id=user_id,
            mission_id=mission_id,
            objective=mission.objective,
            status=mission.status.value,
            domain=mission.domain.value if mission.domain else None,
            target_date=mission.target_date,
            budget=mission.budget,
            constraints_json=json.dumps(list(mission.constraints)),
            preferences_json=json.dumps(list(mission.preferences)),
            related_commitment_ids_json=json.dumps(list(mission.related_commitment_ids)),
            autonomy_grants_json=json.dumps([_autonomy_grant_to_dict(g) for g in mission.autonomy_grants]),
            notes=mission.notes,
            next_step=mission.next_step,
            supersedes_mission_id=mission.supersedes_mission_id,
        )
        self._records.create(record)
        return self._to_domain(record)

    def get_latest(self, *, organization_id: int, user_id: int, mission_id: str) -> Mission | None:
        record = self._records.get_latest_by_mission_id(organization_id, user_id, mission_id)
        return self._to_domain(record) if record else None

    def get_history(self, *, organization_id: int, user_id: int, mission_id: str) -> tuple[Mission, ...]:
        records = self._records.list_history(organization_id, user_id, mission_id)
        return tuple(self._to_domain(record) for record in records)

    def list_active(self, *, organization_id: int, user_id: int) -> tuple[Mission, ...]:
        records = self._records.list_latest_per_mission(organization_id, user_id)
        missions = [self._to_domain(record) for record in records]
        active = [m for m in missions if m.status in ACTIVE_MISSION_STATUSES]
        return tuple(sorted(active, key=lambda m: m.created_at))

    @staticmethod
    def _to_domain(record: MissionRecord) -> Mission:
        created_at = record.created_at if isinstance(record.created_at, datetime) else datetime.fromisoformat(str(record.created_at))
        updated_at = record.updated_at if isinstance(record.updated_at, datetime) else datetime.fromisoformat(str(record.updated_at))
        return Mission(
            mission_id=record.mission_id,
            objective=record.objective,
            status=MissionStatus(record.status),
            domain=LifeDomain(record.domain) if record.domain else None,
            target_date=record.target_date,
            budget=record.budget,
            constraints=tuple(json.loads(record.constraints_json)),
            preferences=tuple(json.loads(record.preferences_json)),
            related_commitment_ids=tuple(json.loads(record.related_commitment_ids_json)),
            autonomy_grants=tuple(_autonomy_grant_from_dict(row) for row in json.loads(record.autonomy_grants_json)),
            notes=record.notes,
            next_step=record.next_step,
            supersedes_mission_id=record.supersedes_mission_id,
            created_at=created_at,
            updated_at=updated_at,
        )


# --- DayEvent (P6.1) --------------------------------------------------------------------------


class SqlDayEventRepository(DayEventRepository):
    """The durable event log - append() always INSERTs, never UPDATEs;
    sequence numbers are computed from the current max in the database
    for that (organization, user, day) key, so ordering survives a
    process restart exactly the way InMemoryDayEventRepository's own
    in-process counter does within one run."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._records = DayEventRecordRepository(db)

    def append(self, event: DayEvent, *, organization_id: int, user_id: int, day_date: date) -> DayEvent:
        sequence = self._records.get_max_sequence(organization_id, user_id, day_date) + 1
        day_mode = event.day_mode
        record = DayEventRecord(
            organization_id=organization_id,
            user_id=user_id,
            day_date=day_date,
            sequence=sequence,
            event_type=event.event_type.value,
            activity_id=event.activity_id,
            description=event.description,
            domain=event.domain.value if event.domain else None,
            deadline=event.deadline,
            estimated_hours=event.estimated_hours,
            reason=event.reason,
            available_hours=event.available_hours,
            day_mode_kind=day_mode.kind.value if day_mode else None,
            day_mode_custom_label=day_mode.custom_label if day_mode else None,
            day_mode_stated_by_user=day_mode.stated_by_user if day_mode else None,
            occurred_at=event.occurred_at,
        )
        self._records.create(record)
        return self._to_domain(record)

    def list_for_day(self, *, organization_id: int, user_id: int, day_date: date) -> tuple[DayEvent, ...]:
        records = self._records.list_for_day(organization_id, user_id, day_date)
        return tuple(self._to_domain(record) for record in records)

    @staticmethod
    def _to_domain(record: DayEventRecord) -> DayEvent:
        occurred_at = record.occurred_at if isinstance(record.occurred_at, datetime) else datetime.fromisoformat(str(record.occurred_at))
        day_mode = None
        if record.day_mode_kind:
            day_mode = DayMode(
                kind=DayModeKind(record.day_mode_kind),
                custom_label=record.day_mode_custom_label or "",
                stated_by_user=bool(record.day_mode_stated_by_user),
            )
        return DayEvent(
            event_type=DayEventType(record.event_type),
            activity_id=record.activity_id,
            description=record.description,
            domain=LifeDomain(record.domain) if record.domain else None,
            deadline=record.deadline,
            estimated_hours=record.estimated_hours,
            reason=record.reason,
            available_hours=record.available_hours,
            day_mode=day_mode,
            occurred_at=occurred_at,
            sequence=record.sequence,
            event_id=str(record.id),
        )


# --- Adaptation (P7.10) --------------------------------------------------------------------------


class SqlAdaptationRepository(AdaptationRepository):
    """Mirrors SqlExperimentRepository's own shape exactly - a real,
    stable adaptation_id (generated once, at the first save) stored in
    its own indexed column and reused across every later lifecycle
    version, since a user may have many concurrent or historical
    adaptations across all four scopes."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._records = AdaptationRecordRepository(db)

    def save(self, adaptation: Adaptation, *, organization_id: int, user_id: int) -> Adaptation:
        from uuid import uuid4

        adaptation_id = adaptation.adaptation_id or str(uuid4())
        record = AdaptationRecord(
            organization_id=organization_id,
            user_id=user_id,
            adaptation_id=adaptation_id,
            scope=adaptation.target.scope.value,
            target_id=adaptation.target.target_id,
            pattern_id=adaptation.pattern_id,
            confidence=adaptation.confidence.value,
            expected_outcome=adaptation.expected_outcome,
            experiment_id=adaptation.experiment_id,
            status=adaptation.status.value,
            supersedes_adaptation_id=adaptation.supersedes_adaptation_id,
            decision_reason=adaptation.decision_reason,
            effect_kind=adaptation.effect.kind.value if adaptation.effect else None,
            effect_direction=adaptation.effect.direction.value if adaptation.effect else None,
        )
        self._records.create(record)
        return self._to_domain(record)

    def get_latest(self, *, organization_id: int, user_id: int, adaptation_id: str) -> Adaptation | None:
        record = self._records.get_latest_by_adaptation_id(organization_id, user_id, adaptation_id)
        return self._to_domain(record) if record else None

    def get_history(self, *, organization_id: int, user_id: int, adaptation_id: str) -> tuple[Adaptation, ...]:
        records = self._records.list_history(organization_id, user_id, adaptation_id)
        return tuple(self._to_domain(record) for record in records)

    def list_active(self, *, organization_id: int, user_id: int) -> tuple[Adaptation, ...]:
        records = self._records.list_latest_per_adaptation(organization_id, user_id)
        adaptations = [self._to_domain(record) for record in records]
        active = [a for a in adaptations if a.status in ACTIVE_ADAPTATION_STATUSES]
        return tuple(sorted(active, key=lambda a: a.created_at))

    def get_adopted_for_target(self, *, organization_id: int, user_id: int, target: AdaptationTarget) -> Adaptation | None:
        for adaptation in self.list_active(organization_id=organization_id, user_id=user_id):
            if adaptation.status == AdaptationStatus.ADOPTED and adaptation.target == target:
                return adaptation
        return None

    @staticmethod
    def _to_domain(record: AdaptationRecord) -> Adaptation:
        created_at = record.created_at if isinstance(record.created_at, datetime) else datetime.fromisoformat(str(record.created_at))
        updated_at = record.updated_at if isinstance(record.updated_at, datetime) else datetime.fromisoformat(str(record.updated_at))
        effect = None
        if record.effect_kind is not None and record.effect_direction is not None:
            effect = AdaptationEffect(kind=AdaptationEffectKind(record.effect_kind), direction=PriorityDirection(record.effect_direction))
        return Adaptation(
            adaptation_id=record.adaptation_id,
            target=AdaptationTarget(scope=AdaptationScope(record.scope), target_id=record.target_id),
            pattern_id=record.pattern_id,
            confidence=Confidence(record.confidence),
            expected_outcome=record.expected_outcome,
            experiment_id=record.experiment_id,
            status=AdaptationStatus(record.status),
            supersedes_adaptation_id=record.supersedes_adaptation_id,
            decision_reason=record.decision_reason,
            effect=effect,
            created_at=created_at,
            updated_at=updated_at,
        )
