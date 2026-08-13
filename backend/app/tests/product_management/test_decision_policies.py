"""DecisionPolicy - default values, mirroring test_discovery_policies.py."""

from app.services.ai.agents.specialists.product_management.product_decision.policies import DecisionPolicy


def test_defaults():
    policy = DecisionPolicy()
    assert policy.default_recall_limit == 10
    assert policy.default_max_context_tokens == 4000
    assert policy.default_list_maximum == 50
    assert policy.minimum_confidence == 0.0


def test_is_frozen():
    policy = DecisionPolicy()
    try:
        policy.minimum_confidence = 0.9  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass
