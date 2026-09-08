"""P7.17 §21: proves the composite unique constraint on day_event_records
actually guards the sequence-collision race Phase 0 found - approved and
applied as a small, additive persistence hardening before /today/interact
was exposed. Not a substitute for real concurrency control; it converts
a silent ordering corruption into a loud, catchable IntegrityError."""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.day_event_record import DayEventRecord
from app.models.user import User


@pytest.fixture()
def user_id(db_session, org_id):
    user = User(
        organization_id=org_id,
        username="carla",
        email="carla@example.com",
        full_name="Carla",
        hashed_password="unused-in-tests",
        roles="viewer",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    return user.id


def test_colliding_sequence_for_the_same_org_user_day_is_rejected(db_session, org_id, user_id):
    first = DayEventRecord(
        organization_id=org_id, user_id=user_id, day_date=date(2026, 1, 1), sequence=1, event_type="activity_added", activity_id="a1", description="First"
    )
    db_session.add(first)
    db_session.commit()

    second = DayEventRecord(
        organization_id=org_id, user_id=user_id, day_date=date(2026, 1, 1), sequence=1, event_type="activity_added", activity_id="a2", description="Second"
    )
    db_session.add(second)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_non_colliding_sequences_are_unaffected(db_session, org_id, user_id):
    for sequence in (1, 2, 3):
        db_session.add(
            DayEventRecord(
                organization_id=org_id, user_id=user_id, day_date=date(2026, 1, 1), sequence=sequence, event_type="activity_added", activity_id=f"a{sequence}", description="x"
            )
        )
    db_session.commit()
    assert db_session.query(DayEventRecord).filter(DayEventRecord.organization_id == org_id).count() == 3


def test_the_same_sequence_number_on_a_different_day_is_unaffected(db_session, org_id, user_id):
    """The constraint is scoped to (organization_id, user_id, day_date,
    sequence) - sequence numbering restarts fresh each day, as it always
    has, and the constraint must not block that."""
    db_session.add(
        DayEventRecord(organization_id=org_id, user_id=user_id, day_date=date(2026, 1, 1), sequence=1, event_type="activity_added", activity_id="a1", description="Day one")
    )
    db_session.add(
        DayEventRecord(organization_id=org_id, user_id=user_id, day_date=date(2026, 1, 2), sequence=1, event_type="activity_added", activity_id="a2", description="Day two")
    )
    db_session.commit()
    assert db_session.query(DayEventRecord).filter(DayEventRecord.organization_id == org_id).count() == 2
