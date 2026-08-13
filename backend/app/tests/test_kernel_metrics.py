import dataclasses

import pytest

from app.services.ai.kernel.metrics import CostEstimate, ExecutionMetrics, TokenUsageReference


# --- TokenUsageReference ---------------------------------------------------------


def test_token_usage_reference_defaults_to_none_fields():
    usage = TokenUsageReference()

    assert usage.prompt_tokens is None
    assert usage.completion_tokens is None
    assert usage.total_tokens is None


def test_token_usage_reference_construction():
    usage = TokenUsageReference(prompt_tokens=10, completion_tokens=5, total_tokens=15)

    assert usage.prompt_tokens == 10
    assert usage.completion_tokens == 5
    assert usage.total_tokens == 15


def test_token_usage_reference_is_frozen():
    usage = TokenUsageReference()

    with pytest.raises(dataclasses.FrozenInstanceError):
        usage.total_tokens = 100


# --- CostEstimate -----------------------------------------------------------------


def test_cost_estimate_construction():
    cost = CostEstimate(amount=0.0042)

    assert cost.amount == 0.0042
    assert cost.currency == "USD"


def test_cost_estimate_custom_currency():
    cost = CostEstimate(amount=1.5, currency="EUR")

    assert cost.currency == "EUR"


def test_cost_estimate_is_frozen():
    cost = CostEstimate(amount=1.0)

    with pytest.raises(dataclasses.FrozenInstanceError):
        cost.amount = 2.0


# --- ExecutionMetrics --------------------------------------------------------------


def test_execution_metrics_defaults():
    metrics = ExecutionMetrics()

    assert metrics.latency_ms is None
    assert metrics.duration_ms is None
    assert metrics.retry_count == 0
    assert metrics.cost_estimate is None
    assert metrics.token_usage is None
    assert metrics.execution_id is None


def test_execution_metrics_execution_id_can_be_set():
    metrics = ExecutionMetrics(execution_id="exec-1")

    assert metrics.execution_id == "exec-1"


def test_execution_metrics_construction_with_all_fields():
    cost = CostEstimate(amount=0.01)
    usage = TokenUsageReference(total_tokens=100)

    metrics = ExecutionMetrics(
        latency_ms=120.5, duration_ms=150.0, retry_count=2, cost_estimate=cost, token_usage=usage
    )

    assert metrics.latency_ms == 120.5
    assert metrics.duration_ms == 150.0
    assert metrics.retry_count == 2
    assert metrics.cost_estimate is cost
    assert metrics.token_usage is usage


def test_execution_metrics_is_frozen():
    metrics = ExecutionMetrics()

    with pytest.raises(dataclasses.FrozenInstanceError):
        metrics.retry_count = 5
