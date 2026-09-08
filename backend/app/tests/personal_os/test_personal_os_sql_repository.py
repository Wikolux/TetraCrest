"""Durable persistence (P2 §6, §13): SqlDailyIntentRepository and
SqlEveningReflectionRepository against a real database (the project's own
db_session fixture - real SQLAlchemy, real SQLite, not a fake), proving
DailyIntent/EveningReflection genuinely survive the repository lifecycle,
not merely that an in-memory dict does."""

from datetime import date

from app.services.personal_os.adaptation import Adaptation, AdaptationEffect, AdaptationTarget
from app.services.personal_os.adaptation_flow import AdaptationFlow
from app.services.personal_os.daily_intent import DailyIntent, IntentField, PlannedActivity
from app.services.personal_os.day_mode import DayMode
from app.services.personal_os.evening import EveningReflection, InMemoryEveningReflectionRepository
from app.services.personal_os.experiment import Experiment, ExperimentBaseline
from app.services.personal_os.life_domain import default_state
from app.services.personal_os.living_day import DayEvent, reconstruct
from app.services.personal_os.mission import AutonomyGrant, Mission
from app.services.personal_os.pattern import Pattern, PatternEvidenceItem
from app.services.personal_os.pattern_flow import PatternDetectionFlow
from app.services.personal_os.reasoning import GrowthRecommendation, Hypothesis, InferredPattern, ObservedFact, UserExplanation
from app.services.personal_os.reconciliation import ReconciliationEvidence, reconcile, reconcile_all
from app.services.personal_os.repository import InMemoryDailyIntentRepository
from app.services.personal_os.shared.types import (
    AdaptationEffectKind,
    AdaptationScope,
    AdaptationStatus,
    AutonomyAction,
    Confidence,
    DayEventType,
    DayModeKind,
    DayType,
    ExperimentStatus,
    ExperimentUserDecision,
    IntentSource,
    LifeDomain,
    LifeDomainStatus,
    MissionStatus,
    PatternStatus,
    PatternType,
    PriorityDirection,
    UserPatternResponse,
)
from app.services.personal_os.sql_repository import (
    SqlAdaptationRepository,
    SqlDailyIntentRepository,
    SqlDayEventRepository,
    SqlEveningReflectionRepository,
    SqlExperimentRepository,
    SqlLifeDomainStateRepository,
    SqlMissionRepository,
    SqlPatternRepository,
)


def _intent(intent_date=date(2026, 8, 13), stated_intention="Work day", day_type=DayType.WORK, **kwargs):
    return DailyIntent(intent_date=intent_date, stated_intention=stated_intention, day_type=day_type, **kwargs)


# --- DailyIntent: create, retrieve, update (new version), history ---------------------------


def test_daily_intent_create_and_retrieve_round_trips_exactly(db_session):
    repo = SqlDailyIntentRepository(db_session)
    original = _intent(
        stated_intention="Ship the milestone",
        day_type=DayType.MIXED,
        planned_activities=(PlannedActivity(description="Write the report", focus_area="writing"),),
        new_priorities=(IntentField(value="Apply for jobs", source=IntentSource.USER_EXPLICIT, confidence=Confidence.HIGH),),
        focus_areas=("career",),
        known_constraints=("only 4 hours available",),
    )
    repo.save(original, organization_id=1, user_id=2)

    fetched = repo.get_for_date(organization_id=1, user_id=2, intent_date=date(2026, 8, 13))
    assert fetched.stated_intention == "Ship the milestone"
    assert fetched.day_type == DayType.MIXED
    assert fetched.planned_activities[0].description == "Write the report"
    assert fetched.new_priorities[0].value == "Apply for jobs"
    assert fetched.new_priorities[0].source == IntentSource.USER_EXPLICIT
    assert fetched.focus_areas == ("career",)
    assert fetched.known_constraints == ("only 4 hours available",)
    assert fetched.intent_id != ""


def test_daily_intent_survives_a_fresh_query_not_just_the_same_session(db_session):
    """Proves durability, not just that the Session's own identity map is
    returning the same Python object back."""
    repo = SqlDailyIntentRepository(db_session)
    repo.save(_intent(stated_intention="Original"), organization_id=1, user_id=2)
    db_session.expire_all()

    fetched = repo.get_for_date(organization_id=1, user_id=2, intent_date=date(2026, 8, 13))
    assert fetched.stated_intention == "Original"


def test_daily_intent_update_creates_a_new_version_never_overwrites(db_session):
    repo = SqlDailyIntentRepository(db_session)
    repo.save(_intent(stated_intention="v1"), organization_id=1, user_id=2)
    repo.save(_intent(stated_intention="v2"), organization_id=1, user_id=2)

    latest = repo.get_for_date(organization_id=1, user_id=2, intent_date=date(2026, 8, 13))
    assert latest.stated_intention == "v2"

    from app.repositories.daily_intent_record_repository import DailyIntentRecordRepository

    all_versions = DailyIntentRecordRepository(db_session).list_by_date_range(1, 2, date(2026, 8, 13), date(2026, 8, 13))
    assert [v.stated_intention for v in all_versions] == ["v1", "v2"]


def test_daily_intent_historical_dates_remain_accessible(db_session):
    repo = SqlDailyIntentRepository(db_session)
    repo.save(_intent(intent_date=date(2026, 8, 10), stated_intention="Monday"), organization_id=1, user_id=2)
    repo.save(_intent(intent_date=date(2026, 8, 11), stated_intention="Tuesday"), organization_id=1, user_id=2)

    assert repo.get_for_date(organization_id=1, user_id=2, intent_date=date(2026, 8, 10)).stated_intention == "Monday"
    assert repo.get_for_date(organization_id=1, user_id=2, intent_date=date(2026, 8, 11)).stated_intention == "Tuesday"


def test_daily_intent_latest_before_finds_the_current_intent(db_session):
    repo = SqlDailyIntentRepository(db_session)
    repo.save(_intent(intent_date=date(2026, 8, 10), stated_intention="Monday"), organization_id=1, user_id=2)

    latest = repo.get_latest_before(organization_id=1, user_id=2, before=date(2026, 8, 13))
    assert latest.stated_intention == "Monday"


def test_daily_intent_repeated_updates_do_not_destroy_history(db_session):
    repo = SqlDailyIntentRepository(db_session)
    for i in range(5):
        repo.save(_intent(stated_intention=f"revision {i}"), organization_id=1, user_id=2)

    from app.repositories.daily_intent_record_repository import DailyIntentRecordRepository

    all_versions = DailyIntentRecordRepository(db_session).list_by_date_range(1, 2, date(2026, 8, 13), date(2026, 8, 13))
    assert len(all_versions) == 5
    assert repo.get_for_date(organization_id=1, user_id=2, intent_date=date(2026, 8, 13)).stated_intention == "revision 4"


def test_daily_intent_scoped_per_organization_and_user(db_session):
    repo = SqlDailyIntentRepository(db_session)
    repo.save(_intent(stated_intention="mine"), organization_id=1, user_id=2)

    assert repo.get_for_date(organization_id=99, user_id=2, intent_date=date(2026, 8, 13)) is None
    assert repo.get_for_date(organization_id=1, user_id=99, intent_date=date(2026, 8, 13)) is None


# --- EveningReflection: create, retrieve, reconciliation persists ---------------------------


def test_evening_reflection_create_and_retrieve_round_trips(db_session):
    repo = SqlEveningReflectionRepository(db_session)
    activity = PlannedActivity(description="Ship the report")
    record = reconcile(activity, ReconciliationEvidence(explicitly_completed=True))
    reflection = EveningReflection(
        reflection_date=date(2026, 8, 13),
        accomplishments=("Shipped the report",),
        lessons=("Start earlier next time",),
    )

    repo.save(reflection, (record,), organization_id=1, user_id=2, daily_intent_id=None)
    db_session.expire_all()

    fetched = repo.get_for_date(organization_id=1, user_id=2, reflection_date=date(2026, 8, 13))
    assert fetched.accomplishments == ("Shipped the report",)
    assert fetched.lessons == ("Start earlier next time",)


def test_evening_reflection_reconciliation_persists_with_evidence(db_session):
    repo = SqlEveningReflectionRepository(db_session)
    activity = PlannedActivity(description="Study AI")
    record = reconcile(activity, ReconciliationEvidence(explicitly_postponed=True, note="ran out of time"))
    reflection = EveningReflection(reflection_date=date(2026, 8, 13))

    repo.save(reflection, (record,), organization_id=1, user_id=2, daily_intent_id=None)
    db_session.expire_all()

    reconciliations = repo.get_reconciliations_for_date(organization_id=1, user_id=2, reflection_date=date(2026, 8, 13))
    assert len(reconciliations) == 1
    assert reconciliations[0].activity.description == "Study AI"
    assert reconciliations[0].status.value == "postponed"
    assert reconciliations[0].evidence.note == "ran out of time"


def test_evening_reflection_links_back_to_its_daily_intent(db_session):
    intent_repo = SqlDailyIntentRepository(db_session)
    saved_intent = intent_repo.save(_intent(stated_intention="Today's plan"), organization_id=1, user_id=2)

    evening_repo = SqlEveningReflectionRepository(db_session)
    reflection = EveningReflection(reflection_date=date(2026, 8, 13))
    evening_repo.save(reflection, (), organization_id=1, user_id=2, daily_intent_id=saved_intent.intent_id)

    from app.repositories.evening_reflection_record_repository import EveningReflectionRecordRepository

    record = EveningReflectionRecordRepository(db_session).get_for_date(1, 2, date(2026, 8, 13))
    assert record.daily_intent_id == int(saved_intent.intent_id)


def test_original_plan_and_actual_outcome_are_both_independently_recoverable(db_session):
    """The exact question §5/§18 require an answer to: "what did I
    originally plan" and "what actually happened" must both still be
    readable, from a fresh query, without one overwriting the other."""
    intent_repo = SqlDailyIntentRepository(db_session)
    evening_repo = SqlEveningReflectionRepository(db_session)

    original = _intent(
        stated_intention="Study AI and ship Tetra OS",
        day_type=DayType.MIXED,
        planned_activities=(PlannedActivity(description="Study AI"), PlannedActivity(description="Ship Tetra OS")),
    )
    intent_repo.save(original, organization_id=1, user_id=2)

    r1 = reconcile(PlannedActivity(description="Study AI"), ReconciliationEvidence(explicitly_postponed=True, note="meeting"))
    r2 = reconcile(PlannedActivity(description="Ship Tetra OS"), ReconciliationEvidence(explicitly_completed=True))
    evening_repo.save(EveningReflection(reflection_date=date(2026, 8, 13)), (r1, r2), organization_id=1, user_id=2, daily_intent_id=None)
    db_session.expire_all()

    what_was_planned = intent_repo.get_for_date(organization_id=1, user_id=2, intent_date=date(2026, 8, 13))
    what_happened = evening_repo.get_reconciliations_for_date(organization_id=1, user_id=2, reflection_date=date(2026, 8, 13))

    assert {a.description for a in what_was_planned.planned_activities} == {"Study AI", "Ship Tetra OS"}
    assert {(r.activity.description, r.status.value) for r in what_happened} == {("Study AI", "postponed"), ("Ship Tetra OS", "completed")}


# --- Pattern (P3 §10, §14): durable persistence of a full nested reasoning chain ------------------


def _full_pattern(status=PatternStatus.PENDING_CONFIRMATION):
    facts = (
        ObservedFact(statement='"Study transformers" postponed on 2026-07-01', evidence_ref="2026-07-01:Study transformers"),
        ObservedFact(statement='"Study transformers" postponed on 2026-07-03', evidence_ref="2026-07-03:Study transformers"),
    )
    explanation = UserExplanation(statement="I kept running out of time in the evenings", explains_activity="Study transformers")
    inferred = InferredPattern(statement="Study transformers was postponed twice.", supporting_facts=facts)
    hypothesis = Hypothesis(statement="Estimates for this activity may be optimistic.", explains=inferred, informed_by=(explanation,))
    recommendation = GrowthRecommendation(statement="Consider a larger time buffer.", responds_to=hypothesis)
    evidence = (
        PatternEvidenceItem(observation_date=date(2026, 7, 1), activity_description="Study transformers", activity_category="learning", status="postponed"),
        PatternEvidenceItem(observation_date=date(2026, 7, 3), activity_description="Study transformers", activity_category="learning", status="postponed"),
    )
    return Pattern(
        pattern_id="",
        pattern_type=PatternType.REPEATED_POSTPONEMENT,
        observation_window_start=date(2026, 7, 1),
        observation_window_end=date(2026, 7, 3),
        evidence=evidence,
        observed_facts=facts,
        pattern_statement="2 learning activities were postponed between 2026-07-01 and 2026-07-03.",
        confidence=Confidence.LOW,
        possible_hypotheses=(hypothesis,),
        recommendation=recommendation,
        status=status,
    )


def test_pattern_round_trips_the_full_nested_reasoning_chain(db_session):
    repo = SqlPatternRepository(db_session)
    saved = repo.save(_full_pattern(), organization_id=1, user_id=2)
    db_session.expire_all()

    fetched = repo.get_latest(organization_id=1, user_id=2, pattern_type=PatternType.REPEATED_POSTPONEMENT)
    assert fetched.pattern_id == saved.pattern_id
    assert fetched.pattern_statement == saved.pattern_statement
    assert fetched.confidence == Confidence.LOW
    assert len(fetched.observed_facts) == 2
    assert len(fetched.possible_hypotheses) == 1
    assert fetched.possible_hypotheses[0].statement == "Estimates for this activity may be optimistic."
    assert fetched.possible_hypotheses[0].informed_by[0].statement == "I kept running out of time in the evenings"
    assert fetched.recommendation.statement == "Consider a larger time buffer."


def test_pattern_survives_a_fresh_session_not_just_the_same_one(db_engine):
    """Proves durability, not just the Session's own identity map -
    mirrors test_daily_intent_survives_a_fresh_query_not_just_the_same_session,
    but with two genuinely independent Sessions against the same engine."""
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    session1 = SessionLocal()
    SqlPatternRepository(session1).save(_full_pattern(), organization_id=1, user_id=2)
    session1.commit()
    session1.close()

    session2 = SessionLocal()
    fetched = SqlPatternRepository(session2).get_latest(organization_id=1, user_id=2, pattern_type=PatternType.REPEATED_POSTPONEMENT)
    assert fetched is not None
    assert fetched.pattern_statement == "2 learning activities were postponed between 2026-07-01 and 2026-07-03."
    session2.close()


def test_pattern_status_change_creates_a_new_version_never_overwrites(db_session):
    from dataclasses import replace

    repo = SqlPatternRepository(db_session)
    first = repo.save(_full_pattern(status=PatternStatus.OBSERVED), organization_id=1, user_id=2)
    repo.save(replace(first, status=PatternStatus.CONFIRMED), organization_id=1, user_id=2)

    latest = repo.get_latest(organization_id=1, user_id=2, pattern_type=PatternType.REPEATED_POSTPONEMENT)
    assert latest.status == PatternStatus.CONFIRMED

    from app.models.pattern_record import PatternRecord

    all_rows = db_session.query(PatternRecord).filter_by(organization_id=1, user_id=2).order_by(PatternRecord.id.asc()).all()
    assert [row.status for row in all_rows] == ["observed", "confirmed"]


def test_list_active_excludes_dismissed_and_superseded(db_session):
    from dataclasses import replace

    repo = SqlPatternRepository(db_session)
    repo.save(_full_pattern(status=PatternStatus.CONFIRMED), organization_id=1, user_id=2)

    dismissed_pattern = replace(_full_pattern(status=PatternStatus.DISMISSED), pattern_type=PatternType.ESTIMATION_ACCURACY)
    repo.save(dismissed_pattern, organization_id=1, user_id=2)

    active = repo.list_active(organization_id=1, user_id=2)
    assert len(active) == 1
    assert active[0].pattern_type == PatternType.REPEATED_POSTPONEMENT


# --- Experiment (P4 §16): durable persistence of the full lifecycle -------------------------------


def _experiment(experiment_id="", status=ExperimentStatus.PROPOSED, review_date=date(2026, 7, 30)):
    baseline = ExperimentBaseline(
        metric="postponement_count", category="learning", period_start=date(2026, 7, 1), period_end=date(2026, 7, 14), value=4.0, observation_count=4
    )
    return Experiment(
        experiment_id=experiment_id,
        pattern_id="pattern-1",
        hypothesis_statement="Estimates for this category may be optimistic.",
        adjustment="Add a 50% buffer to learning-category estimates.",
        measurement_plan="Compare postponement counts against baseline over 14 days.",
        baseline=baseline,
        started_on=date(2026, 7, 16),
        review_date=review_date,
        status=status,
    )


def test_experiment_round_trips_baseline_and_identity(db_session):
    repo = SqlExperimentRepository(db_session)
    saved = repo.save(_experiment(), organization_id=1, user_id=2)
    db_session.expire_all()

    fetched = repo.get_latest(organization_id=1, user_id=2, experiment_id=saved.experiment_id)
    assert fetched.experiment_id == saved.experiment_id
    assert fetched.pattern_id == "pattern-1"
    assert fetched.baseline.value == 4.0
    assert fetched.baseline.observation_count == 4
    assert fetched.baseline.period_start == date(2026, 7, 1)
    assert fetched.status == ExperimentStatus.PROPOSED


def test_experiment_survives_a_fresh_session_not_just_the_same_one(db_engine):
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    session1 = SessionLocal()
    saved = SqlExperimentRepository(session1).save(_experiment(), organization_id=1, user_id=2)
    session1.commit()
    session1.close()

    session2 = SessionLocal()
    fetched = SqlExperimentRepository(session2).get_latest(organization_id=1, user_id=2, experiment_id=saved.experiment_id)
    assert fetched is not None
    assert fetched.baseline.value == 4.0
    session2.close()


def test_experiment_lifecycle_transitions_create_new_versions_never_overwritten(db_session):
    from dataclasses import replace

    repo = SqlExperimentRepository(db_session)
    proposed = repo.save(_experiment(status=ExperimentStatus.PROPOSED), organization_id=1, user_id=2)
    approved = repo.save(replace(proposed, status=ExperimentStatus.APPROVED), organization_id=1, user_id=2)
    repo.save(replace(approved, status=ExperimentStatus.ACTIVE, started_on=date(2026, 7, 16)), organization_id=1, user_id=2)

    history = repo.get_history(organization_id=1, user_id=2, experiment_id=proposed.experiment_id)
    assert [h.status for h in history] == [ExperimentStatus.PROPOSED, ExperimentStatus.APPROVED, ExperimentStatus.ACTIVE]

    latest = repo.get_latest(organization_id=1, user_id=2, experiment_id=proposed.experiment_id)
    assert latest.status == ExperimentStatus.ACTIVE


def test_experiment_comparison_and_decision_round_trip(db_session):
    from dataclasses import replace

    from app.services.personal_os.experiment import ExperimentComparison, ExperimentMeasurement
    from app.services.personal_os.shared.types import ExperimentOutcome

    repo = SqlExperimentRepository(db_session)
    proposed = repo.save(_experiment(), organization_id=1, user_id=2)

    measurement = ExperimentMeasurement(
        metric="postponement_count", category="learning", period_start=date(2026, 7, 16), period_end=date(2026, 7, 30), value=1.0, observation_count=1
    )
    comparison = ExperimentComparison(
        baseline=proposed.baseline,
        measurement=measurement,
        absolute_change=-3.0,
        relative_change=-0.75,
        outcome=ExperimentOutcome.IMPROVED,
        confidence=Confidence.MEDIUM,
        observation_statement="Postponements decreased by 75% during the experiment period (4 to 1).",
    )
    reviewed = repo.save(
        replace(proposed, status=ExperimentStatus.REVIEWED, comparison=comparison, review_narrative="Postponements fell noticeably."),
        organization_id=1,
        user_id=2,
    )
    kept = repo.save(
        replace(reviewed, status=ExperimentStatus.KEPT, decision=ExperimentUserDecision.KEEP, decision_reason="Clear improvement."),
        organization_id=1,
        user_id=2,
    )
    db_session.expire_all()

    fetched = repo.get_latest(organization_id=1, user_id=2, experiment_id=kept.experiment_id)
    assert fetched.status == ExperimentStatus.KEPT
    assert fetched.comparison.outcome == ExperimentOutcome.IMPROVED
    assert fetched.comparison.relative_change == -0.75
    assert fetched.comparison.measurement.value == 1.0
    assert fetched.decision == ExperimentUserDecision.KEEP
    assert fetched.decision_reason == "Clear improvement."


def test_experiment_list_ready_for_review(db_session):
    repo = SqlExperimentRepository(db_session)
    repo.save(_experiment(status=ExperimentStatus.ACTIVE, review_date=date(2026, 7, 30)), organization_id=1, user_id=2)

    not_yet = repo.list_ready_for_review(organization_id=1, user_id=2, today=date(2026, 7, 20))
    assert not_yet == ()

    ready = repo.list_ready_for_review(organization_id=1, user_id=2, today=date(2026, 7, 30))
    assert len(ready) == 1


def test_experiment_list_active_excludes_terminal_statuses(db_session):
    repo = SqlExperimentRepository(db_session)
    repo.save(_experiment(status=ExperimentStatus.ACTIVE), organization_id=1, user_id=2)
    repo.save(_experiment(status=ExperimentStatus.KEPT), organization_id=1, user_id=2)
    repo.save(_experiment(status=ExperimentStatus.STOPPED), organization_id=1, user_id=2)

    active = repo.list_active(organization_id=1, user_id=2)
    assert len(active) == 1
    assert active[0].status == ExperimentStatus.ACTIVE


# --- LifeDomainState (P5 §6): durable persistence of domain activation history --------------------


def test_life_domain_state_round_trips(db_session):
    from dataclasses import replace

    repo = SqlLifeDomainStateRepository(db_session)
    state = replace(default_state(LifeDomain.CAREER), status=LifeDomainStatus.ACTIVE, objective="Find a PM role")
    saved = repo.save(state, organization_id=1, user_id=2)
    db_session.expire_all()

    fetched = repo.get_latest(organization_id=1, user_id=2, domain=LifeDomain.CAREER)
    assert fetched.status == LifeDomainStatus.ACTIVE
    assert fetched.objective == "Find a PM role"
    assert fetched.state_id == saved.state_id


def test_life_domain_state_survives_a_fresh_session(db_engine):
    from dataclasses import replace

    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session1 = SessionLocal()
    SqlLifeDomainStateRepository(session1).save(replace(default_state(LifeDomain.STUDY), status=LifeDomainStatus.ACTIVE), organization_id=1, user_id=2)
    session1.commit()
    session1.close()

    session2 = SessionLocal()
    fetched = SqlLifeDomainStateRepository(session2).get_latest(organization_id=1, user_id=2, domain=LifeDomain.STUDY)
    assert fetched is not None
    assert fetched.status == LifeDomainStatus.ACTIVE
    session2.close()


def test_life_domain_state_transitions_preserve_history(db_session):
    from dataclasses import replace

    repo = SqlLifeDomainStateRepository(db_session)
    active = repo.save(replace(default_state(LifeDomain.CAREER), status=LifeDomainStatus.ACTIVE), organization_id=1, user_id=2)
    repo.save(replace(active, status=LifeDomainStatus.PAUSED), organization_id=1, user_id=2)

    history = repo.get_history(organization_id=1, user_id=2, domain=LifeDomain.CAREER)
    assert [h.status for h in history] == [LifeDomainStatus.ACTIVE, LifeDomainStatus.PAUSED]


def test_life_domain_state_list_all_latest(db_session):
    from dataclasses import replace

    repo = SqlLifeDomainStateRepository(db_session)
    repo.save(replace(default_state(LifeDomain.CAREER), status=LifeDomainStatus.ACTIVE), organization_id=1, user_id=2)
    repo.save(replace(default_state(LifeDomain.BUSINESS), status=LifeDomainStatus.ACTIVE), organization_id=1, user_id=2)

    latest = repo.list_all_latest(organization_id=1, user_id=2)
    assert {s.domain for s in latest} == {LifeDomain.CAREER, LifeDomain.BUSINESS}


# --- Mission (P5 §15): durable persistence including nested AutonomyGrants ------------------------


def _mission_with_grant(status=MissionStatus.DRAFT):
    grant = AutonomyGrant(action=AutonomyAction.RESEARCH, scope="Destination and flight research")
    return Mission(
        mission_id="", objective="Plan a surprise vacation for my wife", status=status,
        domain=LifeDomain.FAMILY, budget="₦500,000", constraints=("dates: 10-20 Dec",), preferences=("beach", "surprise"),
        autonomy_grants=(grant,), next_step="Research beach destinations",
    )


def test_mission_round_trips_including_autonomy_grants(db_session):
    repo = SqlMissionRepository(db_session)
    saved = repo.save(_mission_with_grant(), organization_id=1, user_id=2)
    db_session.expire_all()

    fetched = repo.get_latest(organization_id=1, user_id=2, mission_id=saved.mission_id)
    assert fetched.objective == "Plan a surprise vacation for my wife"
    assert fetched.budget == "₦500,000"
    assert fetched.constraints == ("dates: 10-20 Dec",)
    assert fetched.preferences == ("beach", "surprise")
    assert len(fetched.autonomy_grants) == 1
    assert fetched.autonomy_grants[0].scope == "Destination and flight research"
    assert fetched.autonomy_grants[0].action == AutonomyAction.RESEARCH


def test_mission_survives_a_fresh_session(db_engine):
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session1 = SessionLocal()
    saved = SqlMissionRepository(session1).save(_mission_with_grant(), organization_id=1, user_id=2)
    session1.commit()
    session1.close()

    session2 = SessionLocal()
    fetched = SqlMissionRepository(session2).get_latest(organization_id=1, user_id=2, mission_id=saved.mission_id)
    assert fetched is not None
    assert fetched.objective == "Plan a surprise vacation for my wife"
    session2.close()


def test_mission_lifecycle_transitions_preserve_history(db_session):
    from dataclasses import replace

    repo = SqlMissionRepository(db_session)
    draft = repo.save(_mission_with_grant(status=MissionStatus.DRAFT), organization_id=1, user_id=2)
    active = repo.save(replace(draft, status=MissionStatus.ACTIVE), organization_id=1, user_id=2)
    repo.save(replace(active, status=MissionStatus.COMPLETED), organization_id=1, user_id=2)

    history = repo.get_history(organization_id=1, user_id=2, mission_id=draft.mission_id)
    assert [h.status for h in history] == [MissionStatus.DRAFT, MissionStatus.ACTIVE, MissionStatus.COMPLETED]


def test_mission_list_active_excludes_completed_and_cancelled(db_session):
    repo = SqlMissionRepository(db_session)
    repo.save(_mission_with_grant(status=MissionStatus.ACTIVE), organization_id=1, user_id=2)
    repo.save(_mission_with_grant(status=MissionStatus.COMPLETED), organization_id=1, user_id=2)
    repo.save(_mission_with_grant(status=MissionStatus.CANCELLED), organization_id=1, user_id=2)

    active = repo.list_active(organization_id=1, user_id=2)
    assert len(active) == 1
    assert active[0].status == MissionStatus.ACTIVE


# --- DayEvent (P6.1): durable append-only event log --------------------------------------------


def test_day_event_append_assigns_sequential_sequence_numbers(db_session):
    repo = SqlDayEventRepository(db_session)
    e1 = repo.append(DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="Buy a gift"), organization_id=1, user_id=2, day_date=date(2026, 8, 14))
    e2 = repo.append(DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED, activity_id="a1"), organization_id=1, user_id=2, day_date=date(2026, 8, 14))
    assert e1.sequence == 1
    assert e2.sequence == 2


def test_day_event_round_trips_all_payload_shapes(db_session):
    repo = SqlDayEventRepository(db_session)
    day = date(2026, 8, 14)
    repo.append(DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="Buy a gift", domain=LifeDomain.FAMILY, deadline=date(2026, 8, 20), estimated_hours=1.5), organization_id=1, user_id=2, day_date=day)
    repo.append(DayEvent(event_type=DayEventType.UNEXPECTED_EVENT, activity_id="m1", description="Meeting", estimated_hours=2.0), organization_id=1, user_id=2, day_date=day)
    repo.append(DayEvent(event_type=DayEventType.AVAILABLE_TIME_CHANGED, available_hours=6.0), organization_id=1, user_id=2, day_date=day)
    repo.append(DayEvent(event_type=DayEventType.DAY_MODE_CHANGED, day_mode=DayMode(kind=DayModeKind.FAMILY_FOCUSED)), organization_id=1, user_id=2, day_date=day)
    repo.append(DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED, activity_id="a1", reason="done"), organization_id=1, user_id=2, day_date=day)
    db_session.expire_all()

    events = repo.list_for_day(organization_id=1, user_id=2, day_date=day)
    assert len(events) == 5
    assert events[0].domain == LifeDomain.FAMILY
    assert events[0].deadline == date(2026, 8, 20)
    assert events[0].estimated_hours == 1.5
    assert events[2].available_hours == 6.0
    assert events[3].day_mode.kind == DayModeKind.FAMILY_FOCUSED
    assert events[4].reason == "done"


def test_day_event_survives_a_fresh_session(db_engine):
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session1 = SessionLocal()
    SqlDayEventRepository(session1).append(DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="Buy a gift"), organization_id=1, user_id=2, day_date=date(2026, 8, 14))
    session1.commit()
    session1.close()

    session2 = SessionLocal()
    events = SqlDayEventRepository(session2).list_for_day(organization_id=1, user_id=2, day_date=date(2026, 8, 14))
    assert len(events) == 1
    assert events[0].description == "Buy a gift"
    session2.close()


def test_day_event_reconstructs_correctly_from_durable_storage(db_session):
    repo = SqlDayEventRepository(db_session)
    day = date(2026, 8, 14)
    intent = DailyIntent(intent_date=day, stated_intention="x", day_type=DayType.MIXED, planned_activities=(PlannedActivity(description="Build Tetra Crest"),))
    from app.services.personal_os.living_day import intent_activity_id

    activity_id = intent_activity_id(day, "Build Tetra Crest")
    repo.append(DayEvent(event_type=DayEventType.ACTIVITY_COMPLETED, activity_id=activity_id, reason="finished it"), organization_id=1, user_id=2, day_date=day)
    db_session.expire_all()

    events = repo.list_for_day(organization_id=1, user_id=2, day_date=day)
    state = reconstruct(intent, events, day_date=day)
    assert state.find(activity_id).status.value == "completed"
    assert state.find(activity_id).last_reason == "finished it"


def test_day_event_scoped_by_organization_and_user(db_session):
    repo = SqlDayEventRepository(db_session)
    day = date(2026, 8, 14)
    repo.append(DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="x"), organization_id=1, user_id=2, day_date=day)
    repo.append(DayEvent(event_type=DayEventType.ACTIVITY_ADDED, activity_id="a1", description="x"), organization_id=1, user_id=99, day_date=day)

    assert len(repo.list_for_day(organization_id=1, user_id=2, day_date=day)) == 1


# --- Adaptation (P7.10): durable persistence of the controlled adaptation lifecycle ----------------


def _adaptation(scope=AdaptationScope.USER_PREFERENCE, target_id="2", status=AdaptationStatus.PROPOSED, **kwargs):
    target = AdaptationTarget(scope=scope, target_id=target_id)
    return Adaptation(adaptation_id="", target=target, pattern_id="pattern-1", confidence=Confidence.MEDIUM, status=status, **kwargs)


def test_adaptation_round_trips(db_session):
    repo = SqlAdaptationRepository(db_session)
    saved = repo.save(_adaptation(expected_outcome="Fewer postponements"), organization_id=1, user_id=2)
    db_session.expire_all()

    fetched = repo.get_latest(organization_id=1, user_id=2, adaptation_id=saved.adaptation_id)
    assert fetched.status == AdaptationStatus.PROPOSED
    assert fetched.target.scope == AdaptationScope.USER_PREFERENCE
    assert fetched.target.target_id == "2"
    assert fetched.pattern_id == "pattern-1"
    assert fetched.expected_outcome == "Fewer postponements"


def test_adaptation_effect_round_trips(db_session):
    """P7.11: the structured runtime effect persists and reconstructs
    exactly - the durability §20/§9 requires for behavior to survive a
    process restart, since the Priority flow reads this back through
    AdaptationRepository, never a runtime-only cache."""
    repo = SqlAdaptationRepository(db_session)
    effect = AdaptationEffect(kind=AdaptationEffectKind.PRIORITY_ADJUSTMENT, direction=PriorityDirection.BOOST)
    saved = repo.save(_adaptation(target_id="career", effect=effect), organization_id=1, user_id=2)
    db_session.expire_all()

    fetched = repo.get_latest(organization_id=1, user_id=2, adaptation_id=saved.adaptation_id)
    assert fetched.effect == effect


def test_adaptation_with_no_effect_round_trips_as_none(db_session):
    repo = SqlAdaptationRepository(db_session)
    saved = repo.save(_adaptation(), organization_id=1, user_id=2)
    db_session.expire_all()

    fetched = repo.get_latest(organization_id=1, user_id=2, adaptation_id=saved.adaptation_id)
    assert fetched.effect is None


def test_adaptation_outcome_experiment_id_round_trips(db_session):
    """P7.12: the explicit, durable relationship to a post-adoption
    outcome experiment survives persistence - separate from, and never
    overwriting, `experiment_id` (the pre-adoption evaluation)."""
    from dataclasses import replace

    repo = SqlAdaptationRepository(db_session)
    saved = repo.save(_adaptation(experiment_id="pre-eval-exp"), organization_id=1, user_id=2)
    updated = repo.save(replace(saved, outcome_experiment_id="post-adopt-exp"), organization_id=1, user_id=2)
    db_session.expire_all()

    history = repo.get_history(organization_id=1, user_id=2, adaptation_id=updated.adaptation_id)
    assert history[0].experiment_id == "pre-eval-exp"
    assert history[0].outcome_experiment_id is None
    assert history[-1].experiment_id == "pre-eval-exp"
    assert history[-1].outcome_experiment_id == "post-adopt-exp"


def test_adaptation_survives_a_fresh_session(db_engine):
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session1 = SessionLocal()
    saved = SqlAdaptationRepository(session1).save(_adaptation(), organization_id=1, user_id=2)
    session1.commit()
    session1.close()

    session2 = SessionLocal()
    fetched = SqlAdaptationRepository(session2).get_latest(organization_id=1, user_id=2, adaptation_id=saved.adaptation_id)
    assert fetched is not None
    assert fetched.pattern_id == "pattern-1"
    session2.close()


def test_adaptation_lifecycle_transitions_preserve_history(db_session):
    from dataclasses import replace

    repo = SqlAdaptationRepository(db_session)
    proposed = repo.save(_adaptation(status=AdaptationStatus.PROPOSED), organization_id=1, user_id=2)
    approved = repo.save(replace(proposed, status=AdaptationStatus.APPROVED), organization_id=1, user_id=2)
    repo.save(replace(approved, status=AdaptationStatus.ADOPTED), organization_id=1, user_id=2)

    history = repo.get_history(organization_id=1, user_id=2, adaptation_id=proposed.adaptation_id)
    assert [h.status for h in history] == [AdaptationStatus.PROPOSED, AdaptationStatus.APPROVED, AdaptationStatus.ADOPTED]


def test_adaptation_get_adopted_for_target(db_session):
    repo = SqlAdaptationRepository(db_session)
    target = AdaptationTarget(scope=AdaptationScope.MISSION, target_id="mission-1")
    repo.save(_adaptation(scope=AdaptationScope.MISSION, target_id="mission-1", status=AdaptationStatus.ADOPTED), organization_id=1, user_id=2)
    db_session.expire_all()

    adopted = repo.get_adopted_for_target(organization_id=1, user_id=2, target=target)
    assert adopted is not None
    assert adopted.status == AdaptationStatus.ADOPTED


def test_adaptation_list_active_excludes_terminal_statuses(db_session):
    repo = SqlAdaptationRepository(db_session)
    repo.save(_adaptation(status=AdaptationStatus.ADOPTED), organization_id=1, user_id=2)
    repo.save(_adaptation(status=AdaptationStatus.REJECTED), organization_id=1, user_id=2)
    repo.save(_adaptation(status=AdaptationStatus.SUPERSEDED), organization_id=1, user_id=2)

    active = repo.list_active(organization_id=1, user_id=2)
    assert len(active) == 1
    assert active[0].status == AdaptationStatus.ADOPTED


# --- real path (P7.10 §19): Pattern detection -> Adaptation lifecycle, entirely SQL-backed -----------


def test_real_path_pattern_to_adopted_adaptation_and_back_via_a_fresh_session(db_session, db_engine):
    """Exercises the actual application path, not internal functions in
    isolation: real DailyIntent/EveningReflection evidence -> real
    Pattern detection+confirmation (PatternDetectionFlow) -> real
    Adaptation proposal+approval+adoption (AdaptationFlow) -> real
    Experiment measurement link -> rollback - all against genuine SQL
    persistence, with the final read coming from a completely fresh
    database session (not the same Session's identity map)."""
    intent_repo = InMemoryDailyIntentRepository()
    evening_repo = InMemoryEveningReflectionRepository()
    pattern_repo = SqlPatternRepository(db_session)
    adaptation_repo = SqlAdaptationRepository(db_session)

    org_id, user_id = 1, 7
    for d in (1, 3, 5, 8):
        day = date(2026, 7, d)
        activity = PlannedActivity(description="Study transformers", focus_area="learning")
        intent = DailyIntent(intent_date=day, stated_intention="Study transformers today", day_type=DayType.STUDY, planned_activities=(activity,))
        intent_repo.save(intent, organization_id=org_id, user_id=user_id)
        evidence = {activity.description: ReconciliationEvidence(explicitly_postponed=True, note="ran out of time")}
        reflection = EveningReflection(reflection_date=day, accomplishments=(), evidence_by_activity_description=evidence)
        reconciliations = reconcile_all((activity,), evidence)
        evening_repo.save(reflection, reconciliations, organization_id=org_id, user_id=user_id, daily_intent_id=intent.intent_id)

    pattern_flow = PatternDetectionFlow(intent_repo, evening_repo, pattern_repo)
    pattern_flow.detect(organization_id=org_id, user_id=user_id, today=date(2026, 7, 15))
    surfacing = pattern_flow.surface_next(organization_id=org_id, user_id=user_id)
    confirmed = pattern_flow.respond(organization_id=org_id, user_id=user_id, pattern=surfacing.pattern, response=UserPatternResponse.CONFIRM)
    recommendation = GrowthRecommendation(statement="Add a 50% buffer for learning activities.", responds_to=confirmed.possible_hypotheses[0])
    with_recommendation = pattern_flow.attach_recommendation(organization_id=org_id, user_id=user_id, pattern=confirmed, recommendation=recommendation)

    adaptation_flow = AdaptationFlow(adaptation_repo)
    target = AdaptationTarget(scope=AdaptationScope.USER_PREFERENCE, target_id=str(user_id))
    proposed = adaptation_flow.propose(with_recommendation, organization_id=org_id, user_id=user_id, target=target, expected_outcome="Fewer postponements")
    under_eval = adaptation_flow.begin_evaluation(proposed, organization_id=org_id, user_id=user_id)
    approved = adaptation_flow.approve(under_eval, organization_id=org_id, user_id=user_id, reason="Evidence is clear")
    adopted = adaptation_flow.adopt(approved, organization_id=org_id, user_id=user_id)
    assert adopted.status == AdaptationStatus.ADOPTED
    db_session.commit()

    # a completely fresh session, independent of the one that wrote everything above
    from sqlalchemy.orm import sessionmaker

    fresh_session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)()
    fresh_adaptation_repo = SqlAdaptationRepository(fresh_session)
    fresh_flow = AdaptationFlow(fresh_adaptation_repo)

    rediscovered = fresh_flow.get_adopted(organization_id=org_id, user_id=user_id, target=target)
    assert rediscovered is not None
    assert rediscovered.adaptation_id == adopted.adaptation_id
    assert rediscovered.pattern_id == with_recommendation.pattern_id

    rolled_back = fresh_flow.rollback(rediscovered, organization_id=org_id, user_id=user_id, reason="the buffer made planning feel too rigid")
    fresh_session.commit()
    assert rolled_back.status == AdaptationStatus.ROLLED_BACK
    assert fresh_flow.get_adopted(organization_id=org_id, user_id=user_id, target=target) is None

    history = fresh_adaptation_repo.get_history(organization_id=org_id, user_id=user_id, adaptation_id=adopted.adaptation_id)
    assert [h.status for h in history] == [
        AdaptationStatus.PROPOSED, AdaptationStatus.UNDER_EVALUATION, AdaptationStatus.APPROVED, AdaptationStatus.ADOPTED, AdaptationStatus.ROLLED_BACK,
    ]
    fresh_session.close()


def test_real_path_adopted_priority_effect_changes_living_ranking_across_a_fresh_session(db_session, db_engine):
    """P7.11 §19/§23: extends the P7.10 real path one step further - the
    same real Pattern detection -> Adaptation proposal+approval+adoption
    chain, but this time carrying an explicit PRIORITY_ADJUSTMENT effect,
    read back through a completely fresh SQL session into a real
    PriorityIntelligenceFlow, proving the adopted effect changes an
    actual ranking (not just that the record persists) and that rollback
    removes the change automatically."""
    from app.services.personal_os.adaptation import AdaptationEffect
    from app.services.personal_os.experiment_repository import InMemoryExperimentRepository
    from app.services.personal_os.priority_flow import PriorityIntelligenceFlow
    from app.services.personal_os.shared.types import AdaptationEffectKind, LifeDomain, PriorityDirection

    intent_repo = InMemoryDailyIntentRepository()
    evening_repo = InMemoryEveningReflectionRepository()
    pattern_repo = SqlPatternRepository(db_session)
    adaptation_repo = SqlAdaptationRepository(db_session)
    mission_repo = SqlMissionRepository(db_session)

    org_id, user_id = 1, 11
    for d in (1, 3, 5, 8):
        day = date(2026, 7, d)
        activity = PlannedActivity(description="Follow up with recruiter", focus_area="career")
        intent = DailyIntent(intent_date=day, stated_intention="Follow up on job leads", day_type=DayType.WORK, planned_activities=(activity,))
        intent_repo.save(intent, organization_id=org_id, user_id=user_id)
        evidence = {activity.description: ReconciliationEvidence(explicitly_postponed=True, note="ran out of time")}
        reflection = EveningReflection(reflection_date=day, accomplishments=(), evidence_by_activity_description=evidence)
        reconciliations = reconcile_all((activity,), evidence)
        evening_repo.save(reflection, reconciliations, organization_id=org_id, user_id=user_id, daily_intent_id=intent.intent_id)

    mission_repo.save(
        Mission(mission_id="mission-real", objective="Land a new role", status=MissionStatus.ACTIVE, domain=LifeDomain.CAREER, next_step="Follow up with recruiter"),
        organization_id=org_id,
        user_id=user_id,
    )

    pattern_flow = PatternDetectionFlow(intent_repo, evening_repo, pattern_repo)
    pattern_flow.detect(organization_id=org_id, user_id=user_id, today=date(2026, 7, 15))
    surfacing = pattern_flow.surface_next(organization_id=org_id, user_id=user_id)
    confirmed = pattern_flow.respond(organization_id=org_id, user_id=user_id, pattern=surfacing.pattern, response=UserPatternResponse.CONFIRM)
    recommendation = GrowthRecommendation(statement="Prioritize career follow-ups.", responds_to=confirmed.possible_hypotheses[0])
    with_recommendation = pattern_flow.attach_recommendation(organization_id=org_id, user_id=user_id, pattern=confirmed, recommendation=recommendation)

    adaptation_flow = AdaptationFlow(adaptation_repo)
    target = AdaptationTarget(scope=AdaptationScope.USER_PREFERENCE, target_id=LifeDomain.CAREER.value)
    effect = AdaptationEffect(kind=AdaptationEffectKind.PRIORITY_ADJUSTMENT, direction=PriorityDirection.BOOST)
    proposed = adaptation_flow.propose(with_recommendation, organization_id=org_id, user_id=user_id, target=target, effect=effect)
    approved = adaptation_flow.approve(proposed, organization_id=org_id, user_id=user_id, reason="Evidence is clear")
    adopted = adaptation_flow.adopt(approved, organization_id=org_id, user_id=user_id)
    db_session.commit()

    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    def _ranking_via_fresh_session():
        session = SessionLocal()
        flow = PriorityIntelligenceFlow(
            InMemoryDailyIntentRepository(),
            SqlMissionRepository(session),
            SqlPatternRepository(session),
            InMemoryExperimentRepository(),
            adaptation_repository=SqlAdaptationRepository(session),
        )
        ranking = flow.build_ranking(organization_id=org_id, user_id=user_id, today=date(2026, 7, 16), available_hours=8)
        session.close()
        return next(s for s in ranking.core if s.item.source == "mission")

    boosted_score = _ranking_via_fresh_session()
    assert boosted_score.item.momentum > 0.0

    # rollback, entirely via a fresh session/repository, must remove the effect automatically
    rollback_session = SessionLocal()
    AdaptationFlow(SqlAdaptationRepository(rollback_session)).rollback(adopted, organization_id=org_id, user_id=user_id, reason="No longer needed")
    rollback_session.commit()
    rollback_session.close()

    restored_score = _ranking_via_fresh_session()
    assert restored_score.item.momentum == 0.0


def test_real_path_adaptation_outcome_measured_and_restart_safe_across_fresh_sessions(db_session, db_engine):
    """P7.12: extends the P7.10/P7.11 real-path precedent one step
    further - real Pattern confirmation -> real Adaptation adoption ->
    a real, evidence-backed pre-adoption baseline -> the explicit,
    durable outcome_experiment_id relationship -> a real post-adoption
    measurement and causality-safe comparison -> all read back through a
    COMPLETELY FRESH session, proving restart safety end to end (P7.12
    §15/§17)."""
    from datetime import UTC, datetime, timedelta

    from app.services.personal_os.adaptation_outcome_flow import AdaptationOutcomeFlow
    from app.services.personal_os.experiment_flow import ExperimentFlow
    from app.services.personal_os.pattern_evidence import EvidenceWindow
    from app.services.personal_os.shared.types import ExperimentOutcome
    from app.services.personal_os.sql_repository import SqlExperimentRepository

    intent_repo = InMemoryDailyIntentRepository()
    evening_repo = InMemoryEveningReflectionRepository()
    pattern_repo = SqlPatternRepository(db_session)
    adaptation_repo = SqlAdaptationRepository(db_session)
    experiment_repo = SqlExperimentRepository(db_session)

    org_id, user_id = 1, 13
    today = datetime.now(UTC).date()
    # within PatternDetectionFlow.detect()'s own default trailing-14-day window from `today`,
    # so detect() actually confirms a pattern from this same evidence.
    baseline_dates = [today - timedelta(days=d) for d in (10, 8, 6, 4)]
    post_adoption_dates = [today + timedelta(days=d) for d in (2, 4, 6, 8)]

    for d in baseline_dates:
        activity = PlannedActivity(description="Study transformers", focus_area="learning")
        intent = DailyIntent(intent_date=d, stated_intention="Study", day_type=DayType.STUDY, planned_activities=(activity,))
        intent_repo.save(intent, organization_id=org_id, user_id=user_id)
        evidence = {activity.description: ReconciliationEvidence(explicitly_postponed=True, note="ran out of time")}
        reflection = EveningReflection(reflection_date=d, accomplishments=(), evidence_by_activity_description=evidence)
        reconciliations = reconcile_all((activity,), evidence)
        evening_repo.save(reflection, reconciliations, organization_id=org_id, user_id=user_id, daily_intent_id=intent.intent_id)

    pattern_flow = PatternDetectionFlow(intent_repo, evening_repo, pattern_repo)
    pattern_flow.detect(organization_id=org_id, user_id=user_id, today=today)
    surfacing = pattern_flow.surface_next(organization_id=org_id, user_id=user_id)
    confirmed = pattern_flow.respond(organization_id=org_id, user_id=user_id, pattern=surfacing.pattern, response=UserPatternResponse.CONFIRM)
    recommendation = GrowthRecommendation(statement="Prioritize learning work earlier in the day.", responds_to=confirmed.possible_hypotheses[0])
    with_recommendation = pattern_flow.attach_recommendation(organization_id=org_id, user_id=user_id, pattern=confirmed, recommendation=recommendation)

    adaptation_flow = AdaptationFlow(adaptation_repo)
    target = AdaptationTarget(scope=AdaptationScope.USER_PREFERENCE, target_id=LifeDomain.STUDY.value)
    proposed = adaptation_flow.propose(with_recommendation, organization_id=org_id, user_id=user_id, target=target)
    approved = adaptation_flow.approve(proposed, organization_id=org_id, user_id=user_id, reason="Evidence is clear")
    adopted = adaptation_flow.adopt(approved, organization_id=org_id, user_id=user_id)
    db_session.commit()

    outcome_flow = AdaptationOutcomeFlow(
        adaptation_repo, adaptation_flow, pattern_flow, ExperimentFlow(intent_repo, evening_repo, experiment_repo), experiment_repo
    )
    linked = outcome_flow.propose_outcome_experiment(
        adopted, organization_id=org_id, user_id=user_id, pattern=with_recommendation, hypothesis_statement="h",
        adjustment="Prioritize learning work earlier in the day.", measurement_plan="m", metric="postponement_count", category="learning",
        baseline_window=EvidenceWindow(baseline_dates[0], baseline_dates[-1]),
    )
    db_session.commit()

    for d in post_adoption_dates[:3]:
        activity = PlannedActivity(description="Study transformers", focus_area="learning")
        intent = DailyIntent(intent_date=d, stated_intention="Study", day_type=DayType.STUDY, planned_activities=(activity,))
        intent_repo.save(intent, organization_id=org_id, user_id=user_id)
        evidence = {activity.description: ReconciliationEvidence(explicitly_completed=True)}
        reflection = EveningReflection(reflection_date=d, accomplishments=(), evidence_by_activity_description=evidence)
        reconciliations = reconcile_all((activity,), evidence)
        evening_repo.save(reflection, reconciliations, organization_id=org_id, user_id=user_id, daily_intent_id=intent.intent_id)
    d = post_adoption_dates[3]
    activity = PlannedActivity(description="Study transformers", focus_area="learning")
    intent = DailyIntent(intent_date=d, stated_intention="Study", day_type=DayType.STUDY, planned_activities=(activity,))
    intent_repo.save(intent, organization_id=org_id, user_id=user_id)
    evidence = {activity.description: ReconciliationEvidence(explicitly_postponed=True)}
    reflection = EveningReflection(reflection_date=d, accomplishments=(), evidence_by_activity_description=evidence)
    reconciliations = reconcile_all((activity,), evidence)
    evening_repo.save(reflection, reconciliations, organization_id=org_id, user_id=user_id, daily_intent_id=intent.intent_id)

    # a completely fresh session, independent of the one that wrote everything above
    from sqlalchemy.orm import sessionmaker

    fresh_session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)()
    fresh_adaptation_repo = SqlAdaptationRepository(fresh_session)
    fresh_experiment_repo = SqlExperimentRepository(fresh_session)
    fresh_pattern_repo = SqlPatternRepository(fresh_session)
    fresh_pattern_flow = PatternDetectionFlow(intent_repo, evening_repo, fresh_pattern_repo)
    fresh_adaptation_flow = AdaptationFlow(fresh_adaptation_repo)
    fresh_outcome_flow = AdaptationOutcomeFlow(
        fresh_adaptation_repo, fresh_adaptation_flow, fresh_pattern_flow, ExperimentFlow(intent_repo, evening_repo, fresh_experiment_repo), fresh_experiment_repo
    )

    rediscovered = fresh_adaptation_repo.get_latest(organization_id=org_id, user_id=user_id, adaptation_id=linked.adaptation_id)
    assert rediscovered.outcome_experiment_id == linked.outcome_experiment_id
    assert rediscovered.experiment_id is None  # no pre-adoption evaluation experiment was ever linked - never fabricated

    review = fresh_outcome_flow.review_outcome(rediscovered, organization_id=org_id, user_id=user_id, today=today + timedelta(days=9))
    fresh_session.commit()

    assert review.experiment.comparison.outcome == ExperimentOutcome.IMPROVED
    assert review.experiment.comparison.baseline.observation_count == 4
    assert review.experiment.comparison.measurement.observation_count == 4
    assert review.is_currently_adopted is True
    assert "causality has not been established" in review.recommendation
    fresh_session.close()
