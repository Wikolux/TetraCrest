"""Context-dependent autonomy (P5 §18-§21): mission-scoped permissions,
action-scoped permissions, explicit authorization, unauthorized actions
blocked, financial-consequence actions require authorization, reservation
permission is scoped, and authorization expiration."""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.personal_os.autonomy import REQUIRES_EXPLICIT_AUTHORIZATION, active_grants, is_authorized
from app.services.personal_os.mission import AutonomyGrant
from app.services.personal_os.shared.types import AutonomyAction


def _grant(action, scope="x", **kwargs):
    return AutonomyGrant(action=action, scope=scope, **kwargs)


# --- default-allowed actions (§19: research/analyse/draft/prepare) -------------------------------


@pytest.mark.parametrize("action", [AutonomyAction.OBSERVE, AutonomyAction.RESEARCH, AutonomyAction.PREPARE, AutonomyAction.RECOMMEND, AutonomyAction.ASK])
def test_reversible_actions_are_authorized_by_default(action):
    assert is_authorized((), action=action) is True


# --- always-ask actions (§18-§20) -----------------------------------------------------------------


def test_reserve_is_never_authorized_without_a_grant():
    assert is_authorized((), action=AutonomyAction.RESERVE) is False


def test_execute_is_never_authorized_without_a_grant():
    assert is_authorized((), action=AutonomyAction.EXECUTE) is False


def test_reserve_and_execute_are_the_only_actions_requiring_explicit_authorization():
    assert REQUIRES_EXPLICIT_AUTHORIZATION == frozenset({AutonomyAction.RESERVE, AutonomyAction.EXECUTE})


# --- explicit, scoped authorization (§20) ---------------------------------------------------------


def test_an_explicit_grant_authorizes_its_exact_action():
    grant = _grant(AutonomyAction.RESERVE, scope="Flights matching agreed dates under budget")
    assert is_authorized((grant,), action=AutonomyAction.RESERVE) is True


def test_a_reserve_grant_never_generalizes_to_execute():
    """§20: 'Never infer: User allowed me to reserve flights once,
    therefore I may reserve anything.' - and never across actions
    either."""
    grant = _grant(AutonomyAction.RESERVE, scope="Flights")
    assert is_authorized((grant,), action=AutonomyAction.EXECUTE) is False


def test_a_grant_for_one_mission_does_not_appear_here_because_grants_are_passed_per_mission():
    """AutonomyGrant is nested on Mission, not a global list - the only
    way a grant from a different mission could leak in is if the caller
    passed the wrong mission's own grants tuple, which is on the caller,
    not this function; this test documents that is_authorized() only
    ever sees what it is explicitly given."""
    grant = _grant(AutonomyAction.RESERVE, scope="x")
    assert is_authorized((), action=AutonomyAction.RESERVE) is False
    assert is_authorized((grant,), action=AutonomyAction.RESERVE) is True


# --- revocation and expiration ---------------------------------------------------------------------


def test_revoked_grant_is_not_authorized():
    grant = _grant(AutonomyAction.RESERVE, revoked=True)
    assert is_authorized((grant,), action=AutonomyAction.RESERVE) is False


def test_expired_grant_is_not_authorized():
    grant = _grant(AutonomyAction.RESERVE, expires_at=datetime.now(UTC) - timedelta(days=1))
    assert is_authorized((grant,), action=AutonomyAction.RESERVE) is False


def test_grant_without_expiry_never_expires():
    grant = _grant(AutonomyAction.RESERVE, expires_at=None)
    assert is_authorized((grant,), action=AutonomyAction.RESERVE) is True


def test_grant_not_yet_expired_is_authorized():
    grant = _grant(AutonomyAction.RESERVE, expires_at=datetime.now(UTC) + timedelta(days=1))
    assert is_authorized((grant,), action=AutonomyAction.RESERVE) is True


def test_active_grants_excludes_revoked_and_expired():
    live = _grant(AutonomyAction.RESERVE, scope="live")
    revoked = _grant(AutonomyAction.RESERVE, scope="revoked", revoked=True)
    expired = _grant(AutonomyAction.RESERVE, scope="expired", expires_at=datetime.now(UTC) - timedelta(days=1))
    result = active_grants((live, revoked, expired))
    assert result == (live,)


# --- payment / financial execution (§19) ------------------------------------------------------------


def test_payment_like_execute_action_requires_explicit_authorization():
    """§19: 'Payment requires explicit authorization' / 'Financial
    execution requires explicit authorization unless the user later
    establishes a narrower, explicit rule.'"""
    assert is_authorized((), action=AutonomyAction.EXECUTE) is False
    grant = _grant(AutonomyAction.EXECUTE, scope="Pay the confirmed booking, under the agreed budget")
    assert is_authorized((grant,), action=AutonomyAction.EXECUTE) is True
