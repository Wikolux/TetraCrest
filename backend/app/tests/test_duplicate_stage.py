from datetime import datetime, timezone

from app.services.context.stages.duplicate_stage import DuplicateStage
from app.services.context.types import ContextItem

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _item(resource_id, resource_type="memory", content="content"):
    return ContextItem(
        resource_type=resource_type, resource_id=resource_id, content=content, score=0.5, created_at=_NOW
    )


def test_removes_exact_duplicates_keeping_the_first_occurrence():
    first = _item(1, content="first version")
    duplicate = _item(1, content="second version")
    stage = DuplicateStage()

    result = stage.process([first, duplicate])

    assert result == [first]


def test_preserves_order_of_remaining_items():
    a = _item(1)
    b = _item(2)
    c = _item(3)
    stage = DuplicateStage()

    result = stage.process([a, b, c])

    assert result == [a, b, c]


def test_different_resource_types_with_the_same_id_are_not_duplicates():
    memory_item = _item(1, resource_type="memory")
    message_item = _item(1, resource_type="conversation_message")
    stage = DuplicateStage()

    result = stage.process([memory_item, message_item])

    assert result == [memory_item, message_item]


def test_no_duplicates_returns_all_items_unchanged():
    items = [_item(1), _item(2), _item(3)]
    stage = DuplicateStage()

    assert stage.process(items) == items


def test_empty_input_returns_empty_list():
    stage = DuplicateStage()

    assert stage.process([]) == []


def test_multiple_duplicates_of_the_same_key_are_all_removed():
    first = _item(1, content="v1")
    stage = DuplicateStage()

    result = stage.process([first, _item(1, content="v2"), _item(1, content="v3")])

    assert result == [first]
