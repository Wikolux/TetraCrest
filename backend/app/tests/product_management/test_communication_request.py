"""StakeholderCommunicationRequest/StakeholderCommunicationOperation -
construction, mirroring the request tests of every prior milestone.
"""

from app.services.ai.agents.specialists.product_management.stakeholder_communication.request import (
    StakeholderCommunicationOperation,
    StakeholderCommunicationRequest,
)


def test_operation_is_a_closed_string_enum():
    assert StakeholderCommunicationOperation.DRAFT_COMMUNICATION.value == "draft_communication"
    assert StakeholderCommunicationOperation.MAP_STAKEHOLDER.value == "map_stakeholder"
    assert len(list(StakeholderCommunicationOperation)) == 5


def test_request_defaults():
    request = StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.RECALL)
    assert request.text == ""
    assert request.audience == ""
    assert request.purpose == ""
    assert request.stakeholder_name == ""


def test_request_is_frozen():
    request = StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.RECALL)
    try:
        request.text = "mutated"  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass
