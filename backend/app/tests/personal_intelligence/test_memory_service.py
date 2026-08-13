"""PersonalMemoryService - the thin, domain-typed wrapper over AgentMemory.

No fake ever touches AIMemoryService/MemoryRetrievalPipeline/a real DB -
a hand-rolled _FakeMemory (implementing AgentMemory) records every call
so tests assert on the exact content/memory_type/title passed through,
without depending on MemoryAdapter's own AIMemoryService wiring (already
covered by test_memory_adapter.py).
"""

from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.specialists.personal_intelligence.memory_service import PersonalMemoryService
from app.services.ai.agents.specialists.personal_intelligence.shared.goal import (
    Goal,
    GoalProgressUpdate,
    GoalStatus,
)
from app.services.ai.agents.specialists.personal_intelligence.shared.identity import IdentityAttribute, IdentityFact
from app.services.ai.agents.specialists.personal_intelligence.shared.preference import Preference
from app.services.ai.agents.specialists.personal_intelligence.shared.project import Project
from app.services.ai.agents.specialists.personal_intelligence.shared.reflection import Reflection, ReflectionPeriod
from app.services.ai.agents.specialists.personal_intelligence.shared.types import (
    MEMORY_TYPE_GOAL,
    MEMORY_TYPE_IDENTITY,
    MEMORY_TYPE_PREFERENCE,
    MEMORY_TYPE_PROJECT,
    MEMORY_TYPE_REFLECTION,
)
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


def test_defaults_to_a_memory_adapter_when_none_given():
    # MemoryAdapter's own default pipeline construction eagerly builds a
    # real SemanticSearchService/EmbeddingService, which requires
    # embedding config - not something a unit test should trigger. This
    # only asserts PersonalMemoryService.__init__'s default *type*, via
    # the signature, without instantiating it - mirroring how
    # test_memory_adapter.py never calls MemoryAdapter() with no pipeline
    # either.
    import inspect


    default_memory = inspect.signature(PersonalMemoryService.__init__).parameters["memory"].default
    assert default_memory is None  # falls through to `memory or MemoryAdapter()` in __init__

    source = inspect.getsource(PersonalMemoryService.__init__)
    assert "MemoryAdapter()" in source


def test_uses_the_injected_memory_instance():
    fake = _FakeMemory()
    service = PersonalMemoryService(fake)
    assert service.memory is fake


def test_remember_identity_uses_the_fact_title_and_identity_memory_type():
    fake = _FakeMemory()
    service = PersonalMemoryService(fake)
    fact = IdentityFact(attribute=IdentityAttribute.TIMEZONE, value="America/Los_Angeles")

    service.remember_identity(fact, organization_id=1, user_id=7)

    content, kwargs = fake.remembered[0]
    assert content == fact.to_memory_content()
    assert kwargs == {
        "organization_id": 1,
        "user_id": 7,
        "memory_type": MEMORY_TYPE_IDENTITY,
        "title": fact.title(),
    }


def test_remember_identity_defaults_user_id_to_none():
    fake = _FakeMemory()
    service = PersonalMemoryService(fake)
    service.remember_identity(IdentityFact(attribute=IdentityAttribute.NAME, value="Victor"), organization_id=1)

    assert fake.remembered[0][1]["user_id"] is None


def test_remember_goal_uses_the_goal_title_and_goal_memory_type():
    fake = _FakeMemory()
    service = PersonalMemoryService(fake)
    goal = Goal(title="Ship CP-01")

    service.remember_goal(goal, organization_id=1)

    content, kwargs = fake.remembered[0]
    assert content == goal.to_memory_content()
    assert kwargs["memory_type"] == MEMORY_TYPE_GOAL
    assert kwargs["title"] == "Ship CP-01"


def test_remember_goal_progress_titles_the_memory_with_a_progress_prefix():
    fake = _FakeMemory()
    service = PersonalMemoryService(fake)
    update = GoalProgressUpdate(goal_title="Ship CP-01", note="Made progress", new_status=GoalStatus.COMPLETED)

    service.remember_goal_progress(update, organization_id=1)

    content, kwargs = fake.remembered[0]
    assert content == update.to_memory_content()
    assert kwargs["title"] == "Progress: Ship CP-01"
    assert kwargs["memory_type"] == MEMORY_TYPE_GOAL


def test_remember_project_uses_the_project_name_and_project_memory_type():
    fake = _FakeMemory()
    service = PersonalMemoryService(fake)
    project = Project(name="AI Operating System")

    service.remember_project(project, organization_id=1)

    content, kwargs = fake.remembered[0]
    assert content == project.to_memory_content()
    assert kwargs["memory_type"] == MEMORY_TYPE_PROJECT
    assert kwargs["title"] == "AI Operating System"


def test_remember_reflection_titles_the_memory_with_the_period():
    fake = _FakeMemory()
    service = PersonalMemoryService(fake)
    reflection = Reflection(content="Today went well.", period=ReflectionPeriod.WEEKLY)

    service.remember_reflection(reflection, organization_id=1)

    content, kwargs = fake.remembered[0]
    assert content == reflection.to_memory_content()
    assert kwargs["title"] == "Reflection (weekly)"
    assert kwargs["memory_type"] == MEMORY_TYPE_REFLECTION


def test_remember_preference_titles_the_memory_with_the_category():
    fake = _FakeMemory()
    service = PersonalMemoryService(fake)
    preference = Preference(statement="I prefer concise answers.", category="communication")

    service.remember_preference(preference, organization_id=1)

    content, kwargs = fake.remembered[0]
    assert content == preference.to_memory_content()
    assert kwargs["title"] == "Preference (communication)"
    assert kwargs["memory_type"] == MEMORY_TYPE_PREFERENCE


def test_recall_scopes_retrieval_to_memories_only():
    fake = _FakeMemory()
    service = PersonalMemoryService(fake)

    service.recall("what are my goals", organization_id=1)

    query, kwargs = fake.retrieve_calls[0]
    assert query == "what are my goals"
    assert kwargs["organization_id"] == 1
    assert kwargs["scope"] == "memories"


def test_recall_uses_default_limit_and_max_context_tokens():
    fake = _FakeMemory()
    service = PersonalMemoryService(fake)

    service.recall("query", organization_id=1)

    _, kwargs = fake.retrieve_calls[0]
    assert kwargs["limit"] == 10
    assert kwargs["max_context_tokens"] == 4000


def test_recall_honors_explicit_limit_and_max_context_tokens():
    fake = _FakeMemory()
    service = PersonalMemoryService(fake)

    service.recall("query", organization_id=1, limit=3, max_context_tokens=500)

    _, kwargs = fake.retrieve_calls[0]
    assert kwargs["limit"] == 3
    assert kwargs["max_context_tokens"] == 500


def test_recall_returns_the_context_package_from_memory_retrieve():
    fake = _FakeMemory()
    service = PersonalMemoryService(fake)

    package = service.recall("query", organization_id=1)

    assert isinstance(package, ContextPackage)
