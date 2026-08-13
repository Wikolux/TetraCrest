"""DeliveryRequest/DeliveryOperation - construction and tuple-coercion."""

from app.services.ai.agents.specialists.product_management.delivery.request import DeliveryOperation, DeliveryRequest


def test_operation_is_a_closed_string_enum():
    assert DeliveryOperation.GENERATE_RECOMMENDATION.value == "generate_recommendation"
    assert DeliveryOperation.PLAN_SPRINT.value == "plan_sprint"
    assert len(list(DeliveryOperation)) == 13


def test_request_defaults():
    request = DeliveryRequest(operation=DeliveryOperation.RECALL)
    assert request.text == ""
    assert request.items == ()
    assert request.dependencies == ()
    assert request.capacity is None
    assert request.planned_load is None


def test_request_coerces_list_fields_to_tuples():
    request = DeliveryRequest(
        operation=DeliveryOperation.PLAN_SPRINT,
        items=["a", "b"],
        dependencies=["auth"],
        planned=["a"],
        actual=["a", "b"],
    )
    assert request.items == ("a", "b")
    assert request.dependencies == ("auth",)
    assert request.planned == ("a",)
    assert request.actual == ("a", "b")


def test_request_is_frozen():
    request = DeliveryRequest(operation=DeliveryOperation.RECALL)
    try:
        request.text = "mutated"  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass
