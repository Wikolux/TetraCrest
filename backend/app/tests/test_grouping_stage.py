from datetime import datetime, timezone

from app.services.context.stages.grouping_stage import GroupingStage
from app.services.context.types import BudgetedItems, ContextItem

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _item(resource_id, resource_type="memory"):
    return ContextItem(
        resource_type=resource_type, resource_id=resource_id, content="content", score=0.5, created_at=_NOW
    )


def test_groups_items_by_resource_type():
    memory_1 = _item(1, "memory")
    memory_2 = _item(2, "memory")
    message_1 = _item(3, "conversation_message")
    stage = GroupingStage()

    result = stage.process(BudgetedItems(items=[memory_1, memory_2, message_1], estimated_tokens=0, truncated=False))

    assert result.groups == {"memory": [memory_1, memory_2], "conversation_message": [message_1]}


def test_preserves_item_order_within_each_group():
    first = _item(1, "memory")
    second = _item(2, "memory")
    third = _item(3, "memory")
    stage = GroupingStage()

    result = stage.process(BudgetedItems(items=[third, first, second], estimated_tokens=0, truncated=False))

    assert result.groups["memory"] == [third, first, second]


def test_groups_ordered_by_first_appearance_in_input():
    message_item = _item(1, "conversation_message")
    memory_item = _item(2, "memory")
    stage = GroupingStage()

    result = stage.process(
        BudgetedItems(items=[message_item, memory_item], estimated_tokens=0, truncated=False)
    )

    assert list(result.groups.keys()) == ["conversation_message", "memory"]


def test_carries_forward_estimated_tokens_and_truncated_unchanged():
    stage = GroupingStage()

    result = stage.process(BudgetedItems(items=[_item(1)], estimated_tokens=42, truncated=True))

    assert result.estimated_tokens == 42
    assert result.truncated is True


def test_empty_input_returns_empty_groups():
    stage = GroupingStage()

    result = stage.process(BudgetedItems(items=[], estimated_tokens=0, truncated=False))

    assert result.groups == {}
