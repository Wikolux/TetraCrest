"""Adaptation domain objects (P7.10): AdaptationTarget validation,
Adaptation validation and defaults, and the governance-boundary
guarantee that AdaptationScope cannot represent governed configuration."""

import pytest

from app.services.personal_os.adaptation import Adaptation, AdaptationTarget
from app.services.personal_os.shared.types import AdaptationScope, AdaptationStatus, Confidence


def test_adaptation_target_requires_a_target_id():
    with pytest.raises(ValueError):
        AdaptationTarget(scope=AdaptationScope.USER, target_id="")


def test_adaptation_target_scope_and_target_id_round_trip():
    target = AdaptationTarget(scope=AdaptationScope.MISSION, target_id="mission-1")
    assert target.scope == AdaptationScope.MISSION
    assert target.target_id == "mission-1"


def test_adaptation_requires_a_pattern_id():
    target = AdaptationTarget(scope=AdaptationScope.USER, target_id="1")
    with pytest.raises(ValueError):
        Adaptation(adaptation_id="", target=target, pattern_id="", confidence=Confidence.LOW)


def test_adaptation_defaults_to_proposed():
    target = AdaptationTarget(scope=AdaptationScope.USER, target_id="1")
    adaptation = Adaptation(adaptation_id="", target=target, pattern_id="p1", confidence=Confidence.MEDIUM)
    assert adaptation.status == AdaptationStatus.PROPOSED
    assert adaptation.supersedes_adaptation_id is None
    assert adaptation.experiment_id is None


# --- governance boundary (§10): AdaptationScope cannot represent governed configuration -----------


def test_adaptation_scope_has_exactly_the_four_named_scopes():
    assert {s.value for s in AdaptationScope} == {"user", "user_preference", "mission", "workflow"}


@pytest.mark.parametrize("fragment", ["auth", "security", "tenant", "permission", "governance", "policy", "credential", "secret", "deploy"])
def test_no_adaptation_scope_resembles_governed_configuration(fragment):
    for scope in AdaptationScope:
        assert fragment not in scope.value


def test_adaptation_target_cannot_be_constructed_with_a_scope_outside_the_enum():
    """The structural guarantee itself: there is no way to name a scope
    that isn't one of the four - AdaptationScope is a closed StrEnum, so
    passing anything else raises before an AdaptationTarget can even be
    built."""
    with pytest.raises(ValueError):
        AdaptationScope("agent_behavior")
    with pytest.raises(ValueError):
        AdaptationScope("organization_policy")
    with pytest.raises(ValueError):
        AdaptationScope("capability")
