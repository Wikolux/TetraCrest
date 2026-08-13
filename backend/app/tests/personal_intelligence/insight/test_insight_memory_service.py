"""InsightMemoryService - remember_insight()/recall_insights() (via
AgentMemory, identical mechanism to PersonalMemoryService) and
list_memory_facts() (via AIMemoryService.list_memories(), the platform's
existing bulk-listing method - unmodified, just paginated and filtered
client-side). No fake here ever touches a real DB.
"""

from datetime import UTC, datetime, timedelta

from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.specialists.personal_intelligence.insight.memory_service import InsightMemoryService
from app.services.ai.agents.specialists.personal_intelligence.shared.insight import Insight, InsightType
from app.services.context.types import ContextPackage


class _FakeMemory(AgentMemory):
    def __init__(self):
        self.remembered = []
        self.retrieve_calls = []

    def remember(self, item, **kwargs):
        self.remembered.append((item, kwargs))

    def retrieve(self, query, **kwargs):
        self.retrieve_calls.append((query, kwargs))
        return ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)

    def forget(self, item_id):
        raise NotImplementedError

    def search(self, query, **kwargs):
        raise NotImplementedError


class _Row:
    def __init__(self, id, content, memory_type, title, created_at):
        self.id = id
        self.content = content
        self.memory_type = memory_type
        self.title = title
        self.created_at = created_at


class _FakeMemoryService:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def list_memories(self, organization_id, skip=0, limit=20):
        self.calls.append((organization_id, skip, limit))
        return self.rows[skip : skip + limit]


def _row(id_, content="content", memory_type="personal_goal", title=None, created_at=None):
    return _Row(id_, content, memory_type, title, created_at or datetime.now(UTC))


# --- remember_insight -------------------------------------------------------------------------


def test_remember_insight_uses_the_insight_title_and_personal_insight_memory_type():
    fake = _FakeMemory()
    service = InsightMemoryService(fake, _FakeMemoryService([]))
    insight = Insight(insight_type=InsightType.PATTERN, title="Recurring theme: 'x'", observation="y")

    service.remember_insight(insight, organization_id=1, user_id=7)

    content, kwargs = fake.remembered[0]
    assert content == insight.to_memory_content()
    assert kwargs == {"organization_id": 1, "user_id": 7, "memory_type": "personal_insight", "title": insight.title}


def test_remember_insight_defaults_user_id_to_none():
    fake = _FakeMemory()
    service = InsightMemoryService(fake, _FakeMemoryService([]))
    service.remember_insight(Insight(insight_type=InsightType.PATTERN, title="x", observation="y"), organization_id=1)

    assert fake.remembered[0][1]["user_id"] is None


# --- recall_insights ---------------------------------------------------------------------------


def test_recall_insights_scopes_retrieval_to_memories_only():
    fake = _FakeMemory()
    service = InsightMemoryService(fake, _FakeMemoryService([]))

    service.recall_insights("what patterns do you see", organization_id=1)

    query, kwargs = fake.retrieve_calls[0]
    assert query == "what patterns do you see"
    assert kwargs["organization_id"] == 1
    assert kwargs["scope"] == "memories"


def test_recall_insights_uses_default_limit_and_max_context_tokens():
    fake = _FakeMemory()
    service = InsightMemoryService(fake, _FakeMemoryService([]))

    service.recall_insights("query", organization_id=1)

    _, kwargs = fake.retrieve_calls[0]
    assert kwargs["limit"] == 10
    assert kwargs["max_context_tokens"] == 4000


def test_recall_insights_honors_explicit_limit_and_max_context_tokens():
    fake = _FakeMemory()
    service = InsightMemoryService(fake, _FakeMemoryService([]))

    service.recall_insights("query", organization_id=1, limit=3, max_context_tokens=500)

    _, kwargs = fake.retrieve_calls[0]
    assert kwargs["limit"] == 3
    assert kwargs["max_context_tokens"] == 500


def test_recall_insights_returns_a_context_package():
    fake = _FakeMemory()
    service = InsightMemoryService(fake, _FakeMemoryService([]))
    package = service.recall_insights("query", organization_id=1)
    assert isinstance(package, ContextPackage)


# --- list_memory_facts ---------------------------------------------------------------------------


def test_list_memory_facts_converts_rows_to_context_items():
    now = datetime.now(UTC)
    rows = [_row(1, content="Goal content", memory_type="personal_goal", title="A Goal", created_at=now)]
    service = InsightMemoryService(_FakeMemory(), _FakeMemoryService(rows))

    items = service.list_memory_facts(1)

    assert len(items) == 1
    assert items[0].resource_type == "memory"
    assert items[0].resource_id == 1
    assert items[0].content == "Goal content"
    assert items[0].metadata == {"memory_type": "personal_goal", "title": "A Goal"}


def test_list_memory_facts_defaults_title_to_empty_string_when_none():
    rows = [_row(1, title=None)]
    service = InsightMemoryService(_FakeMemory(), _FakeMemoryService(rows))
    items = service.list_memory_facts(1)
    assert items[0].metadata["title"] == ""


def test_list_memory_facts_paginates_through_list_memories():
    rows = [_row(i) for i in range(1, 251)]  # more than one default page (100)
    memsvc = _FakeMemoryService(rows)
    service = InsightMemoryService(_FakeMemory(), memsvc)

    items = service.list_memory_facts(1, maximum=250)

    assert len(items) == 250
    assert [item.resource_id for item in items] == list(range(1, 251))
    assert len(memsvc.calls) == 3  # 100 + 100 + 50


def test_list_memory_facts_stops_paginating_once_a_short_page_is_returned():
    rows = [_row(i) for i in range(1, 51)]
    memsvc = _FakeMemoryService(rows)
    service = InsightMemoryService(_FakeMemory(), memsvc)

    items = service.list_memory_facts(1, maximum=200)

    assert len(items) == 50
    assert len(memsvc.calls) == 1


def test_list_memory_facts_respects_the_maximum_cap():
    rows = [_row(i) for i in range(1, 500)]
    service = InsightMemoryService(_FakeMemory(), _FakeMemoryService(rows))

    items = service.list_memory_facts(1, maximum=30)

    assert len(items) == 30


def test_list_memory_facts_filters_by_memory_types_when_given():
    rows = [
        _row(1, memory_type="personal_goal"),
        _row(2, memory_type="personal_preference"),
        _row(3, memory_type="personal_goal"),
    ]
    service = InsightMemoryService(_FakeMemory(), _FakeMemoryService(rows))

    items = service.list_memory_facts(1, memory_types=frozenset({"personal_goal"}))

    assert {item.resource_id for item in items} == {1, 3}


def test_list_memory_facts_with_no_memory_types_filter_returns_everything():
    rows = [_row(1, memory_type="personal_goal"), _row(2, memory_type="personal_preference")]
    service = InsightMemoryService(_FakeMemory(), _FakeMemoryService(rows))

    items = service.list_memory_facts(1)

    assert len(items) == 2


def test_list_memory_facts_filters_by_since_cutoff():
    now = datetime.now(UTC)
    rows = [
        _row(1, created_at=now - timedelta(days=60)),
        _row(2, created_at=now - timedelta(days=5)),
    ]
    service = InsightMemoryService(_FakeMemory(), _FakeMemoryService(rows))

    items = service.list_memory_facts(1, since=now - timedelta(days=30))

    assert [item.resource_id for item in items] == [2]


def test_list_memory_facts_with_no_since_returns_everything_regardless_of_age():
    now = datetime.now(UTC)
    rows = [_row(1, created_at=now - timedelta(days=3650))]
    service = InsightMemoryService(_FakeMemory(), _FakeMemoryService(rows))

    items = service.list_memory_facts(1)

    assert len(items) == 1


def test_list_memory_facts_on_an_empty_organization_returns_nothing():
    service = InsightMemoryService(_FakeMemory(), _FakeMemoryService([]))
    assert service.list_memory_facts(1) == ()


def test_defaults_to_memory_adapter_and_ai_memory_service_when_none_given():
    # Both defaults eagerly construct real, DB/embedding-backed
    # collaborators - not something a unit test should trigger. This
    # only asserts the constructor's default *types*, via the signature,
    # without instantiating them - mirroring
    # test_memory_service.py::test_defaults_to_a_memory_adapter_when_none_given.
    import inspect

    params = inspect.signature(InsightMemoryService.__init__).parameters
    assert params["memory"].default is None
    assert params["memory_service"].default is None
    source = inspect.getsource(InsightMemoryService.__init__)
    assert "MemoryAdapter()" in source
    assert "AIMemoryService()" in source
