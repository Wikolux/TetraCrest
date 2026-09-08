"""ExecutionRecordRepository (P7.16): the durable, pre-commit operational
execution ledger - create_started()/mark_succeeded()/mark_failed()/
get_by_execution_id()/list_non_terminal(), tenant isolation, transition
invariants, and the central proof this milestone exists to produce: a
STARTED record survives an interruption and is discoverable from a
COMPLETELY FRESH database session, exactly like every prior milestone's
own "fresh session" restart-safety proofs (P7.10-P7.15)."""

from datetime import datetime

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.enums import ExecutionStatus
from app.repositories.execution_record_repository import ExecutionRecordRepository

ORG_ID, USER_ID = 1, 7


def test_create_started_persists_a_started_record(db_session):
    repo = ExecutionRecordRepository(db_session)

    record = repo.create_started(execution_id="exec-1", organization_id=ORG_ID, user_id=USER_ID, agent_id="research", operation="research.lookup")

    assert record.status == ExecutionStatus.STARTED.value
    assert record.finished_at is None
    assert isinstance(record.started_at, datetime)


def test_mark_succeeded_transitions_from_started(db_session):
    repo = ExecutionRecordRepository(db_session)
    repo.create_started(execution_id="exec-2", organization_id=ORG_ID, operation="research.lookup")

    record = repo.mark_succeeded("exec-2")

    assert record.status == ExecutionStatus.SUCCEEDED.value
    assert record.finished_at is not None


def test_mark_failed_transitions_from_started_and_stores_error_summary(db_session):
    repo = ExecutionRecordRepository(db_session)
    repo.create_started(execution_id="exec-3", organization_id=ORG_ID, operation="research.lookup")

    record = repo.mark_failed("exec-3", error_summary="OpenAI request failed: timeout")

    assert record.status == ExecutionStatus.FAILED.value
    assert record.error_summary == "OpenAI request failed: timeout"


def test_mark_terminal_raises_for_unknown_execution_id(db_session):
    repo = ExecutionRecordRepository(db_session)

    with pytest.raises(ValueError, match="No ExecutionRecord found"):
        repo.mark_succeeded("does-not-exist")


# --- transition invariants (P7.16 §12): terminal outcomes are immutable ----------------------


def test_succeeded_cannot_transition_to_failed(db_session):
    repo = ExecutionRecordRepository(db_session)
    repo.create_started(execution_id="exec-4", organization_id=ORG_ID, operation="research.lookup")
    repo.mark_succeeded("exec-4")

    with pytest.raises(ValueError, match="terminal outcomes are immutable"):
        repo.mark_failed("exec-4")


def test_failed_cannot_transition_to_succeeded(db_session):
    repo = ExecutionRecordRepository(db_session)
    repo.create_started(execution_id="exec-5", organization_id=ORG_ID, operation="research.lookup")
    repo.mark_failed("exec-5")

    with pytest.raises(ValueError, match="terminal outcomes are immutable"):
        repo.mark_succeeded("exec-5")


def test_started_cannot_be_reasserted_back_to_started_via_terminal_methods(db_session):
    """There is no public method to move a record backward to STARTED at
    all - mark_succeeded()/mark_failed() are the only transitions this
    repository exposes, and both require the current status to be
    STARTED, so a terminal row can never be "reset"."""
    repo = ExecutionRecordRepository(db_session)
    repo.create_started(execution_id="exec-6", organization_id=ORG_ID, operation="research.lookup")
    repo.mark_succeeded("exec-6")

    record = repo.get_by_execution_id("exec-6", organization_id=ORG_ID)
    assert record.status == ExecutionStatus.SUCCEEDED.value


# --- fetch / non-terminal discovery -----------------------------------------------------------


def test_get_by_execution_id_returns_the_record(db_session):
    repo = ExecutionRecordRepository(db_session)
    repo.create_started(execution_id="exec-7", organization_id=ORG_ID, operation="research.lookup")

    record = repo.get_by_execution_id("exec-7", organization_id=ORG_ID)

    assert record is not None
    assert record.execution_id == "exec-7"


def test_get_by_execution_id_returns_none_for_unknown_id(db_session):
    repo = ExecutionRecordRepository(db_session)
    assert repo.get_by_execution_id("nope", organization_id=ORG_ID) is None


def test_list_non_terminal_returns_only_started_records(db_session):
    repo = ExecutionRecordRepository(db_session)
    repo.create_started(execution_id="exec-8", organization_id=ORG_ID, operation="research.lookup")
    repo.create_started(execution_id="exec-9", organization_id=ORG_ID, operation="research.lookup")
    repo.mark_succeeded("exec-9")

    non_terminal = repo.list_non_terminal(organization_id=ORG_ID)

    assert {r.execution_id for r in non_terminal} == {"exec-8"}


# --- tenant isolation (P7.16 §29/§30) ----------------------------------------------------------


def test_get_by_execution_id_never_returns_a_record_from_another_organization(db_session):
    repo = ExecutionRecordRepository(db_session)
    repo.create_started(execution_id="exec-org-a", organization_id=ORG_ID, operation="research.lookup")

    other_org_result = repo.get_by_execution_id("exec-org-a", organization_id=ORG_ID + 1)

    assert other_org_result is None


def test_list_non_terminal_never_returns_another_organizations_records(db_session):
    repo = ExecutionRecordRepository(db_session)
    repo.create_started(execution_id="exec-org-b", organization_id=ORG_ID, operation="research.lookup")

    other_org_results = repo.list_non_terminal(organization_id=ORG_ID + 1)

    assert other_org_results == []


def test_list_non_terminal_scoped_by_user_when_requested(db_session):
    repo = ExecutionRecordRepository(db_session)
    repo.create_started(execution_id="exec-user-a", organization_id=ORG_ID, user_id=1, operation="research.lookup")
    repo.create_started(execution_id="exec-user-b", organization_id=ORG_ID, user_id=2, operation="research.lookup")

    user_a_results = repo.list_non_terminal(organization_id=ORG_ID, user_id=1)

    assert {r.execution_id for r in user_a_results} == {"exec-user-a"}


# --- the central proof of P7.16: durable persistence across a genuinely fresh session --------


def test_started_record_survives_interruption_and_is_discoverable_from_a_fresh_session(db_engine):
    """The core proof this milestone exists to produce: create_started()
    is committed, and NOTHING further ever runs (simulating the process
    dying before any terminal update) - a completely fresh session/engine
    connection, constructed independently, can still discover the record
    and confirm it is exactly STARTED. This is not an in-memory object
    check - it is a real, separate SQLAlchemy Session against the same
    underlying database, proving durability, not merely correct Python
    logic within one session's own identity map."""
    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    writing_session = SessionLocal()
    ExecutionRecordRepository(writing_session).create_started(
        execution_id="exec-crash", organization_id=ORG_ID, user_id=USER_ID, agent_id="research", operation="research.lookup"
    )
    writing_session.close()
    # --- simulated process interruption: nothing else ever runs ---

    fresh_session = SessionLocal()
    fresh_repo = ExecutionRecordRepository(fresh_session)
    discovered = fresh_repo.get_by_execution_id("exec-crash", organization_id=ORG_ID)

    assert discovered is not None
    assert discovered.status == ExecutionStatus.STARTED.value
    assert discovered.finished_at is None

    non_terminal = fresh_repo.list_non_terminal(organization_id=ORG_ID)
    assert "exec-crash" in {r.execution_id for r in non_terminal}
    fresh_session.close()


def test_started_record_does_not_claim_an_external_side_effect_occurred(db_session):
    """P7.16 §17: a STARTED record may legitimately exist even when the
    external request was never actually sent (e.g. the process died
    between committing STARTED and calling httpx) - this test documents
    that the repository itself makes no claim either way; STARTED means
    only "Tetra durably began the workflow," never "the external system
    received the request." Nothing about the record's own shape asserts
    otherwise (no field named anything like "external_call_sent")."""
    repo = ExecutionRecordRepository(db_session)
    record = repo.create_started(execution_id="exec-no-side-effect", organization_id=ORG_ID, operation="research.lookup")

    assert not hasattr(record, "external_call_sent")
    assert not hasattr(record, "side_effect_confirmed")
    assert record.status == ExecutionStatus.STARTED.value
