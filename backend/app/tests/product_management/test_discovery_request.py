"""DiscoveryRequest/DiscoveryOperation - construction and tuple-coercion,
mirroring test_personal_intelligence_agent.py's own PersonalIntelligenceRequest
coverage style.
"""

from app.services.ai.agents.specialists.product_management.discovery.request import DiscoveryOperation, DiscoveryRequest


def test_operation_is_a_closed_string_enum():
    assert DiscoveryOperation.VALIDATE_PROBLEM.value == "validate_problem"
    assert DiscoveryOperation.RECALL.value == "recall"
    assert len(list(DiscoveryOperation)) == 12


def test_request_defaults():
    request = DiscoveryRequest(operation=DiscoveryOperation.RECALL)
    assert request.text == ""
    assert request.jobs == ()
    assert request.pains == ()
    assert request.goals == ()


def test_request_coerces_list_fields_to_tuples():
    request = DiscoveryRequest(
        operation=DiscoveryOperation.FRAME_PERSONA,
        jobs=["ship fast"],
        pains=["slow tools"],
        goals=["grow revenue"],
    )
    assert request.jobs == ("ship fast",)
    assert request.pains == ("slow tools",)
    assert request.goals == ("grow revenue",)


def test_request_is_frozen():
    request = DiscoveryRequest(operation=DiscoveryOperation.RECALL)
    try:
        request.text = "mutated"  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass
