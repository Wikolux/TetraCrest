from datetime import datetime, timezone

from app.services.context.stages.budget_stage import BudgetStage
from app.services.context.types import ContextItem

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _item(resource_id, content):
    return ContextItem(
        resource_type="memory", resource_id=resource_id, content=content, score=0.5, created_at=_NOW
    )


def test_token_estimation_uses_content_length_divided_by_four():
    # "a" * 40 -> 40 // 4 = 10 tokens
    stage = BudgetStage(max_tokens=100)

    result = stage.process([_item(1, "a" * 40)])

    assert result.estimated_tokens == 10


def test_token_estimation_uses_integer_division():
    # "a" * 7 -> 7 // 4 = 1 token, not 1.75
    stage = BudgetStage(max_tokens=100)

    result = stage.process([_item(1, "a" * 7)])

    assert result.estimated_tokens == 1


def test_all_items_kept_when_well_under_budget():
    items = [_item(1, "a" * 8), _item(2, "a" * 8)]  # 2 + 2 = 4 tokens
    stage = BudgetStage(max_tokens=100)

    result = stage.process(items)

    assert result.items == items
    assert result.estimated_tokens == 4
    assert result.truncated is False


def test_truncates_when_items_exceed_budget():
    first = _item(1, "a" * 40)  # 10 tokens
    second = _item(2, "a" * 40)  # 10 tokens
    third = _item(3, "a" * 40)  # 10 tokens
    stage = BudgetStage(max_tokens=15)  # only room for the first item

    result = stage.process([first, second, third])

    assert result.items == [first]
    assert result.estimated_tokens == 10
    assert result.truncated is True


def test_prefix_is_strictly_ordered_never_skips_an_oversized_item_for_a_smaller_one():
    huge = _item(1, "a" * 400)  # 100 tokens, way over budget
    small = _item(2, "a" * 4)  # 1 token, would easily fit alone
    stage = BudgetStage(max_tokens=10)

    result = stage.process([huge, small])

    assert result.items == []  # stops at the first item that doesn't fit
    assert result.truncated is True


def test_exact_fit_is_not_truncated():
    item = _item(1, "a" * 40)  # exactly 10 tokens
    stage = BudgetStage(max_tokens=10)

    result = stage.process([item])

    assert result.items == [item]
    assert result.estimated_tokens == 10
    assert result.truncated is False


def test_first_item_alone_exceeding_budget_yields_empty_result():
    huge = _item(1, "a" * 400)  # 100 tokens
    stage = BudgetStage(max_tokens=10)

    result = stage.process([huge])

    assert result.items == []
    assert result.estimated_tokens == 0
    assert result.truncated is True


def test_empty_input_returns_empty_untruncated_result():
    stage = BudgetStage(max_tokens=100)

    result = stage.process([])

    assert result.items == []
    assert result.estimated_tokens == 0
    assert result.truncated is False
