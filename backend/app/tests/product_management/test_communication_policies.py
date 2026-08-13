"""CommunicationPolicy - default values, mirroring every prior milestone's
own minimal coverage.
"""

from app.services.ai.agents.specialists.product_management.stakeholder_communication.policies import CommunicationPolicy


def test_defaults():
    policy = CommunicationPolicy()
    assert policy.default_recall_limit == 10
    assert policy.default_max_context_tokens == 4000
    assert policy.default_list_maximum == 50
    assert policy.minimum_confidence == 0.0


def test_is_frozen():
    policy = CommunicationPolicy()
    try:
        policy.minimum_confidence = 0.9  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass
