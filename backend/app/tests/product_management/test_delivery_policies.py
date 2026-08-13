"""DeliveryPolicy - default values, mirroring test_discovery_policies.py's/
test_decision_policies.py's own minimal coverage.
"""

from app.services.ai.agents.specialists.product_management.delivery.policies import DeliveryPolicy


def test_defaults():
    policy = DeliveryPolicy()
    assert policy.default_recall_limit == 10
    assert policy.default_max_context_tokens == 4000
    assert policy.default_list_maximum == 50
    assert policy.minimum_confidence == 0.0


def test_is_frozen():
    policy = DeliveryPolicy()
    try:
        policy.minimum_confidence = 0.9  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass
