import pytest

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.factory import AgentFactory
from app.services.ai.agents.registry import AgentRegistry
from app.services.ai.agents.types import AgentError, AgentIdentity
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeResponse


class _FakeAgent(BaseAgent):
    def __init__(self, identity):
        super().__init__(identity)

    def initialize(self) -> None:
        return None

    def execute(self, context: AgentContext) -> RuntimeResponse:
        return RuntimeResponse(success=True)

    def pause(self) -> None:
        return None

    def resume(self) -> None:
        return None

    def cancel(self) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def health(self) -> bool:
        return True

    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities()

    def permissions(self) -> tuple[str, ...]:
        return ()

    def memory(self):
        return None

    def planner(self):
        return None

    def runtime(self) -> AIRuntime:
        return AIRuntime()


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(AgentRegistry._providers)
    AgentRegistry._providers.clear()
    yield
    AgentRegistry._providers.clear()
    AgentRegistry._providers.update(original)


def test_create_raises_for_an_unknown_agent():
    with pytest.raises(AgentError, match="Unknown agent"):
        AgentFactory.create("research")


def test_create_constructs_the_registered_agent_class():
    AgentRegistry.register("research", _FakeAgent)
    identity = AgentIdentity(agent_id="agent-1", name="research", display_name="Research Agent")

    agent = AgentFactory.create("research", identity)

    assert isinstance(agent, _FakeAgent)
    assert agent.identity is identity


def test_exists_reflects_registry_state():
    assert AgentFactory.exists("research") is False

    AgentRegistry.register("research", _FakeAgent)

    assert AgentFactory.exists("research") is True


def test_available_lists_every_registered_agent_name():
    AgentRegistry.register("research", _FakeAgent)
    AgentRegistry.register("planner", _FakeAgent)

    assert set(AgentFactory.available()) == {"research", "planner"}


def test_available_is_empty_when_nothing_is_registered():
    assert AgentFactory.available() == ()


def test_the_factory_never_needs_to_change_when_a_new_agent_is_registered():
    # AgentFactory.create has no knowledge of "_FakeAgent" - it is purely
    # a registry lookup, so registering a brand-new agent class works
    # without touching factory.py
    class _AnotherAgent(_FakeAgent):
        pass

    AgentRegistry.register("another", _AnotherAgent)

    agent = AgentFactory.create("another", AgentIdentity(agent_id="a2", name="another", display_name="Another"))

    assert isinstance(agent, _AnotherAgent)
