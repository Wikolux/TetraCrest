"""DecisionRequest/DecisionOperation - construction and tuple-coercion."""

from app.services.ai.agents.specialists.product_management.product_decision.request import (
    DecisionOperation,
    DecisionRequest,
)


def test_operation_is_a_closed_string_enum():
    assert DecisionOperation.GENERATE_RECOMMENDATION.value == "generate_recommendation"
    assert DecisionOperation.RECALL_DECISION_HISTORY.value == "recall_decision_history"
    assert len(list(DecisionOperation)) == 10


def test_request_defaults():
    request = DecisionRequest(operation=DecisionOperation.RECALL_DECISION_HISTORY)
    assert request.question == ""
    assert request.options == ()
    assert request.criteria == ()
    assert request.assumptions == ()
    assert request.reach is None


def test_request_coerces_list_fields_to_tuples():
    request = DecisionRequest(
        operation=DecisionOperation.COMPARE_OPTIONS,
        options=["build", "buy"],
        criteria=["cost"],
        assumptions=["market is stable"],
    )
    assert request.options == ("build", "buy")
    assert request.criteria == ("cost",)
    assert request.assumptions == ("market is stable",)


def test_request_is_frozen():
    request = DecisionRequest(operation=DecisionOperation.RECALL_DECISION_HISTORY)
    try:
        request.question = "mutated"  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass
