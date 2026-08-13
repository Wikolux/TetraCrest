"""DiscoveryPolicy - default values, mirroring test_research_policies.py's
own minimal coverage."""

from app.services.ai.agents.specialists.product_management.discovery.policies import DiscoveryPolicy


def test_defaults():
    policy = DiscoveryPolicy()
    assert policy.default_recall_limit == 10
    assert policy.default_max_context_tokens == 4000
    assert policy.default_list_maximum == 50
    assert policy.minimum_confidence == 0.0


def test_is_frozen():
    policy = DiscoveryPolicy()
    try:
        policy.minimum_confidence = 0.9  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass
