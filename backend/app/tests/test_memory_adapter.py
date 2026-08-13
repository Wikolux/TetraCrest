from datetime import UTC, datetime

import pytest

from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
from app.services.context.types import ContextItem, ContextPackage, ContextSection


class _FakePipeline:
    def __init__(self, package=None):
        self.package = package or ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)
        self.memory_calls = []
        self.conversation_calls = []
        self.all_calls = []

    def search_memories(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.memory_calls.append((query, organization_id, limit, max_context_tokens))
        return self.package

    def search_conversation_messages(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.conversation_calls.append((query, organization_id, limit, max_context_tokens))
        return self.package

    def search_all(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.all_calls.append((query, organization_id, limit, max_context_tokens))
        return self.package


def _package_with_one_item():
    item = ContextItem(resource_type="memory", resource_id=1, content="fact", score=1.0, created_at=datetime.now(UTC))
    section = ContextSection(resource_type="memory", items=[item])
    return ContextPackage(sections=[section], estimated_tokens=4, item_count=1, truncated=False)


# --- MemoryAdapter is a real AgentMemory -----------------------------------------------------


def test_memory_adapter_is_an_agent_memory():
    assert issubclass(MemoryAdapter, AgentMemory)
    assert isinstance(MemoryAdapter(pipeline=_FakePipeline()), AgentMemory)


# --- retrieve() routes by scope, reusing the existing passthroughs, no new retrieval logic ----


def test_retrieve_defaults_to_scope_all():
    pipeline = _FakePipeline()
    adapter = MemoryAdapter(pipeline=pipeline)

    adapter.retrieve("query", organization_id=1)

    assert pipeline.all_calls == [("query", 1, 10, 4000)]
    assert pipeline.memory_calls == []
    assert pipeline.conversation_calls == []


def test_retrieve_scope_memories_routes_to_search_memories():
    pipeline = _FakePipeline()
    adapter = MemoryAdapter(pipeline=pipeline)

    adapter.retrieve("query", organization_id=1, scope="memories")

    assert pipeline.memory_calls == [("query", 1, 10, 4000)]
    assert pipeline.all_calls == []


def test_retrieve_scope_conversations_routes_to_search_conversation_messages():
    pipeline = _FakePipeline()
    adapter = MemoryAdapter(pipeline=pipeline)

    adapter.retrieve("query", organization_id=1, scope="conversations")

    assert pipeline.conversation_calls == [("query", 1, 10, 4000)]
    assert pipeline.all_calls == []


def test_retrieve_passes_through_limit_and_max_context_tokens():
    pipeline = _FakePipeline()
    adapter = MemoryAdapter(pipeline=pipeline)

    adapter.retrieve("query", organization_id=1, limit=5, max_context_tokens=1000)

    assert pipeline.all_calls == [("query", 1, 5, 1000)]


def test_retrieve_returns_the_pipelines_context_package():
    package = _package_with_one_item()
    adapter = MemoryAdapter(pipeline=_FakePipeline(package=package))

    result = adapter.retrieve("query", organization_id=1)

    assert result is package


def test_retrieve_rejects_an_unknown_scope():
    adapter = MemoryAdapter(pipeline=_FakePipeline())

    with pytest.raises(ValueError, match="Unknown retrieval scope"):
        adapter.retrieve("query", organization_id=1, scope="bogus")


def test_retrieve_requires_organization_id():
    adapter = MemoryAdapter(pipeline=_FakePipeline())

    with pytest.raises(KeyError):
        adapter.retrieve("query")


# --- search() is retrieve(), not a second implementation --------------------------------------


def test_search_delegates_to_retrieve_with_the_default_scope():
    pipeline = _FakePipeline()
    adapter = MemoryAdapter(pipeline=pipeline)

    adapter.search("query", organization_id=1)

    assert pipeline.all_calls == [("query", 1, 10, 4000)]


def test_search_accepts_the_same_scope_kwarg_as_retrieve():
    pipeline = _FakePipeline()
    adapter = MemoryAdapter(pipeline=pipeline)

    adapter.search("query", organization_id=1, scope="memories")

    assert pipeline.memory_calls == [("query", 1, 10, 4000)]


# --- retrieve_memories/retrieve_conversations/retrieve_all are unchanged ----------------------


def test_original_retrieve_memories_method_still_works_unchanged():
    pipeline = _FakePipeline()
    adapter = MemoryAdapter(pipeline=pipeline)

    adapter.retrieve_memories("query", 1)

    assert pipeline.memory_calls == [("query", 1, 10, 4000)]


def test_original_retrieve_conversations_method_still_works_unchanged():
    pipeline = _FakePipeline()
    adapter = MemoryAdapter(pipeline=pipeline)

    adapter.retrieve_conversations("query", 1)

    assert pipeline.conversation_calls == [("query", 1, 10, 4000)]


def test_original_retrieve_all_method_still_works_unchanged():
    pipeline = _FakePipeline()
    adapter = MemoryAdapter(pipeline=pipeline)

    adapter.retrieve_all("query", 1)

    assert pipeline.all_calls == [("query", 1, 10, 4000)]


# --- remember() / forget() (CP-01.2): real, AIMemoryService-backed ---------------------------


class _FakeMemory:
    def __init__(self, id, organization_id, content, user_id=None, memory_type="general", title=None):
        self.id = id
        self.organization_id = organization_id
        self.content = content
        self.user_id = user_id
        self.memory_type = memory_type
        self.title = title


class _FakeMemoryService:
    def __init__(self):
        self.created = []
        self.deleted = []
        self._next_id = 1

    def create_memory(self, organization_id, content, user_id=None, memory_type="general", title=None):
        memory = _FakeMemory(self._next_id, organization_id, content, user_id, memory_type, title)
        self._next_id += 1
        self.created.append(memory)
        return memory

    def delete_memory(self, memory_id, organization_id):
        self.deleted.append((memory_id, organization_id))
        return True


def test_remember_creates_a_memory_via_the_memory_service():
    service = _FakeMemoryService()
    adapter = MemoryAdapter(pipeline=_FakePipeline(), memory_service=service)

    adapter.remember("User prefers concise answers.", organization_id=1)

    assert len(service.created) == 1
    assert service.created[0].content == "User prefers concise answers."
    assert service.created[0].organization_id == 1
    assert service.created[0].memory_type == "general"


def test_remember_passes_through_user_id_memory_type_and_title():
    service = _FakeMemoryService()
    adapter = MemoryAdapter(pipeline=_FakePipeline(), memory_service=service)

    adapter.remember(
        "Learn Spanish", organization_id=1, user_id=7, memory_type="personal_goal", title="Learn Spanish"
    )

    created = service.created[0]
    assert created.user_id == 7
    assert created.memory_type == "personal_goal"
    assert created.title == "Learn Spanish"


def test_remember_coerces_a_non_string_item_to_text():
    service = _FakeMemoryService()
    adapter = MemoryAdapter(pipeline=_FakePipeline(), memory_service=service)

    adapter.remember(42, organization_id=1)

    assert service.created[0].content == "42"


def test_remember_returns_none():
    service = _FakeMemoryService()
    adapter = MemoryAdapter(pipeline=_FakePipeline(), memory_service=service)

    result = adapter.remember("fact", organization_id=1)

    assert result is None


def test_remember_requires_organization_id():
    adapter = MemoryAdapter(pipeline=_FakePipeline(), memory_service=_FakeMemoryService())

    with pytest.raises(KeyError):
        adapter.remember("fact")


def test_forget_deletes_via_the_memory_service():
    service = _FakeMemoryService()
    adapter = MemoryAdapter(pipeline=_FakePipeline(), memory_service=service)

    adapter.forget("1:42")

    assert service.deleted == [(42, 1)]


def test_forget_rejects_a_malformed_item_id():
    adapter = MemoryAdapter(pipeline=_FakePipeline(), memory_service=_FakeMemoryService())

    with pytest.raises(ValueError, match="organization_id:memory_id"):
        adapter.forget("not-a-valid-id")


def test_forget_rejects_a_non_numeric_item_id():
    adapter = MemoryAdapter(pipeline=_FakePipeline(), memory_service=_FakeMemoryService())

    with pytest.raises(ValueError, match="organization_id:memory_id"):
        adapter.forget("abc:def")


def test_memory_service_defaults_when_not_injected():
    # Constructing without an explicit memory_service must not raise -
    # AIMemoryService() itself degrades gracefully with no embedding
    # config, the same way every other default construction in this
    # platform does.
    adapter = MemoryAdapter(pipeline=_FakePipeline())

    assert adapter.memory_service is not None
