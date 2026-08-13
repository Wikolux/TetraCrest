"""PersonalStateReader (§5): reads through AgentMemory only - never a
raw DB query, never a direct import of CP-01/CP-02 specialist code."""

from datetime import UTC, datetime

from app.services.ai.agents.memory import AgentMemory
from app.services.context.types import ContextItem, ContextPackage, ContextSection
from app.services.personal_os.personal_state import PersonalStateReader


class _FakeMemory(AgentMemory):
    """Mirrors test_discovery_agent.py's own _FakeMemory exactly - a
    hand-written fake, never a mock."""

    def __init__(self, package=None):
        self.package = package or ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)
        self.retrieve_calls = []

    def remember(self, item, **kwargs):
        raise NotImplementedError

    def retrieve(self, query, **kwargs):
        self.retrieve_calls.append((query, kwargs))
        return self.package

    def search(self, query, **kwargs):
        return self.retrieve(query, **kwargs)

    def forget(self, item_id):
        raise NotImplementedError


def _package_for(memory_type: str, content: str) -> ContextPackage:
    item = ContextItem(
        resource_type="memory",
        resource_id=1,
        content=content,
        score=1.0,
        created_at=datetime.now(UTC),
        metadata={"memory_type": memory_type},
    )
    return ContextPackage(sections=[ContextSection(resource_type="memory", items=[item])], estimated_tokens=10, item_count=1, truncated=False)


def test_reader_reads_only_through_agent_memory_retrieve():
    memory = _FakeMemory(package=_package_for("personal_goal", "Ship the launch"))
    reader = PersonalStateReader(memory=memory)

    state = reader.read(organization_id=1)

    assert len(state.goals) == 1
    assert state.goals[0].content == "Ship the launch"
    assert len(memory.retrieve_calls) == 7  # one call per state domain this phase implements


def test_reader_scopes_reads_by_organization_id():
    memory = _FakeMemory()
    PersonalStateReader(memory=memory).read(organization_id=42)
    for _query, kwargs in memory.retrieve_calls:
        assert kwargs["organization_id"] == 42


def test_reader_uses_the_memories_scope_never_conversations():
    memory = _FakeMemory()
    PersonalStateReader(memory=memory).read(organization_id=1)
    for _query, kwargs in memory.retrieve_calls:
        assert kwargs["scope"] == "memories"


def test_undeclared_domains_are_empty_not_fabricated():
    """Messages, meetings, opportunities, and financial signals have no
    real data source this phase - they must be empty, never populated
    with invented content."""
    memory = _FakeMemory()
    state = PersonalStateReader(memory=memory).read(organization_id=1)
    assert state.messages == ()
    assert state.meetings == ()
    assert state.opportunities == ()
    assert state.financial_signals == ()


def test_has_active_commitments_reflects_real_reads():
    empty_state = PersonalStateReader(memory=_FakeMemory()).read(organization_id=1)
    assert empty_state.has_active_commitments is False

    populated = PersonalStateReader(memory=_FakeMemory(package=_package_for("personal_goal", "x"))).read(organization_id=1)
    assert populated.has_active_commitments is True
