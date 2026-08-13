"""StrategyRequest/StrategyOperation - construction and tuple-coercion."""

from app.services.ai.agents.specialists.product_management.strategy_portfolio.request import (
    StrategyOperation,
    StrategyRequest,
)


def test_operation_is_a_closed_string_enum():
    assert StrategyOperation.GENERATE_RECOMMENDATION.value == "generate_recommendation"
    assert StrategyOperation.ASSESS_PORTFOLIO.value == "assess_portfolio"
    assert len(list(StrategyOperation)) == 11


def test_request_defaults():
    request = StrategyRequest(operation=StrategyOperation.RECALL)
    assert request.text == ""
    assert request.items == ()
    assert request.products == ()
    assert request.key_results == ()


def test_request_coerces_list_fields_to_tuples():
    request = StrategyRequest(
        operation=StrategyOperation.ASSESS_PORTFOLIO,
        items=["a", "b"],
        products=["Product A", "Product B"],
        key_results=["kr1"],
    )
    assert request.items == ("a", "b")
    assert request.products == ("Product A", "Product B")
    assert request.key_results == ("kr1",)


def test_request_is_frozen():
    request = StrategyRequest(operation=StrategyOperation.RECALL)
    try:
        request.text = "mutated"  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass
