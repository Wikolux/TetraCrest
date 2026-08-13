from datetime import datetime, timezone

from app.services.context.types import (
    BudgetedItems,
    ContextItem,
    ContextPackage,
    ContextSection,
    GroupedItems,
)

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _item(resource_id=1, resource_type="memory"):
    return ContextItem(
        resource_type=resource_type,
        resource_id=resource_id,
        content="some content",
        score=0.5,
        created_at=_NOW,
    )


def test_context_item_construction():
    item = ContextItem(
        resource_type="memory",
        resource_id=1,
        content="hello",
        score=0.9,
        created_at=_NOW,
        metadata={"organization_id": 7},
    )

    assert item.resource_type == "memory"
    assert item.resource_id == 1
    assert item.content == "hello"
    assert item.score == 0.9
    assert item.created_at == _NOW
    assert item.metadata == {"organization_id": 7}


def test_context_item_metadata_defaults_to_none():
    item = _item()

    assert item.metadata is None


def test_context_section_defaults_to_empty_items():
    section = ContextSection(resource_type="memory")

    assert section.items == []


def test_context_section_holds_items():
    items = [_item(1), _item(2)]

    section = ContextSection(resource_type="memory", items=items)

    assert section.items == items


def test_context_package_construction():
    section = ContextSection(resource_type="memory", items=[_item(1)])

    package = ContextPackage(sections=[section], estimated_tokens=10, item_count=1, truncated=False)

    assert package.sections == [section]
    assert package.estimated_tokens == 10
    assert package.item_count == 1
    assert package.truncated is False


def test_budgeted_items_construction():
    items = [_item(1)]

    budgeted = BudgetedItems(items=items, estimated_tokens=5, truncated=True)

    assert budgeted.items == items
    assert budgeted.estimated_tokens == 5
    assert budgeted.truncated is True


def test_grouped_items_construction():
    groups = {"memory": [_item(1)]}

    grouped = GroupedItems(groups=groups, estimated_tokens=5, truncated=False)

    assert grouped.groups == groups
    assert grouped.estimated_tokens == 5
    assert grouped.truncated is False
