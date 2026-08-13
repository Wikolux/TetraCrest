from datetime import datetime, timezone

from app.services.context.stages.formatter_stage import FormatterStage
from app.services.context.types import ContextItem, ContextPackage, GroupedItems

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _item(resource_id, resource_type="memory"):
    return ContextItem(
        resource_type=resource_type, resource_id=resource_id, content="content", score=0.5, created_at=_NOW
    )


def test_converts_groups_into_context_sections():
    memory_items = [_item(1), _item(2)]
    message_items = [_item(3, "conversation_message")]
    stage = FormatterStage()

    package = stage.process(
        GroupedItems(
            groups={"memory": memory_items, "conversation_message": message_items},
            estimated_tokens=10,
            truncated=False,
        )
    )

    assert isinstance(package, ContextPackage)
    assert len(package.sections) == 2
    assert package.sections[0].resource_type == "memory"
    assert package.sections[0].items == memory_items
    assert package.sections[1].resource_type == "conversation_message"
    assert package.sections[1].items == message_items


def test_item_count_sums_items_across_all_sections():
    stage = FormatterStage()

    package = stage.process(
        GroupedItems(
            groups={"memory": [_item(1), _item(2)], "conversation_message": [_item(3)]},
            estimated_tokens=0,
            truncated=False,
        )
    )

    assert package.item_count == 3


def test_carries_forward_estimated_tokens_and_truncated():
    stage = FormatterStage()

    package = stage.process(GroupedItems(groups={}, estimated_tokens=99, truncated=True))

    assert package.estimated_tokens == 99
    assert package.truncated is True


def test_empty_groups_produce_empty_sections_and_zero_item_count():
    stage = FormatterStage()

    package = stage.process(GroupedItems(groups={}, estimated_tokens=0, truncated=False))

    assert package.sections == []
    assert package.item_count == 0


def test_produces_no_markdown_or_prompt_text():
    # structured output only - item content passes through completely
    # unchanged, never wrapped in any formatting
    stage = FormatterStage()
    item = _item(1)
    original_content = item.content

    package = stage.process(GroupedItems(groups={"memory": [item]}, estimated_tokens=0, truncated=False))

    assert package.sections[0].items[0].content == original_content
