"""Adaptation domain objects (P7.10): AdaptationTarget validation,
Adaptation validation and defaults, and the governance-boundary
guarantee that AdaptationScope cannot represent governed configuration."""

import pytest

from app.services.personal_os.adaptation import Adaptation, AdaptationEffect, AdaptationTarget
from app.services.personal_os.shared.types import AdaptationEffectKind, AdaptationScope, AdaptationStatus, Confidence, LifeDomain, PriorityDirection


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
    assert adaptation.outcome_experiment_id is None


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


# --- runtime effect (P7.11): explicit and structured, never inferred, bounded by construction ------


def test_adaptation_defaults_to_no_effect():
    target = AdaptationTarget(scope=AdaptationScope.USER, target_id="1")
    adaptation = Adaptation(adaptation_id="", target=target, pattern_id="p1", confidence=Confidence.MEDIUM)
    assert adaptation.effect is None


def test_user_preference_priority_adjustment_effect_requires_a_life_domain_target_id():
    target = AdaptationTarget(scope=AdaptationScope.USER_PREFERENCE, target_id="not-a-real-domain")
    effect = AdaptationEffect(kind=AdaptationEffectKind.PRIORITY_ADJUSTMENT, direction=PriorityDirection.BOOST)
    with pytest.raises(ValueError):
        Adaptation(adaptation_id="", target=target, pattern_id="p1", confidence=Confidence.MEDIUM, effect=effect)


def test_user_preference_priority_adjustment_effect_accepts_a_life_domain_target_id():
    target = AdaptationTarget(scope=AdaptationScope.USER_PREFERENCE, target_id=LifeDomain.CAREER.value)
    effect = AdaptationEffect(kind=AdaptationEffectKind.PRIORITY_ADJUSTMENT, direction=PriorityDirection.BOOST)
    adaptation = Adaptation(adaptation_id="", target=target, pattern_id="p1", confidence=Confidence.MEDIUM, effect=effect)
    assert adaptation.effect == effect


def test_mission_priority_adjustment_effect_does_not_require_a_life_domain_target_id():
    target = AdaptationTarget(scope=AdaptationScope.MISSION, target_id="mission-42")
    effect = AdaptationEffect(kind=AdaptationEffectKind.PRIORITY_ADJUSTMENT, direction=PriorityDirection.SUPPRESS)
    adaptation = Adaptation(adaptation_id="", target=target, pattern_id="p1", confidence=Confidence.MEDIUM, effect=effect)
    assert adaptation.effect == effect


def test_adaptation_effect_kind_has_exactly_one_named_member():
    """P7.11 §3/§8: exactly one runtime effect family exists this
    milestone - a deliberately closed vocabulary, never a generic rule
    language."""
    assert {k.value for k in AdaptationEffectKind} == {"priority_adjustment"}
