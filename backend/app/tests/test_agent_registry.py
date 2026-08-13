import pytest

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.registry import AgentRegistry
from app.services.ai.agents.types import AgentError
from app.services.ai.shared.provider_registry import GenericProviderRegistry


def test_registry_is_built_on_the_generic_registry_not_a_parallel_type():
    assert issubclass(AgentRegistry, GenericProviderRegistry)


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(AgentRegistry._providers)
    AgentRegistry._providers.clear()
    yield
    AgentRegistry._providers.clear()
    AgentRegistry._providers.update(original)


def test_registry_starts_empty():
    assert AgentRegistry.get("research") is None
    assert AgentRegistry.all_registered() == {}


def test_register_and_get_an_agent_class():
    AgentRegistry.register("research", BaseAgent)

    assert AgentRegistry.get("research") is BaseAgent


def test_is_registered_reflects_registration_state():
    assert AgentRegistry.is_registered("research") is False

    AgentRegistry.register("research", BaseAgent)

    assert AgentRegistry.is_registered("research") is True


def test_registering_an_already_registered_name_raises_by_default():
    AgentRegistry.register("research", BaseAgent)

    with pytest.raises(AgentError, match="already registered"):
        AgentRegistry.register("research", BaseAgent)


def test_registering_with_overwrite_true_replaces_the_previous_registration():
    class _OtherAgent(BaseAgent):
        pass

    AgentRegistry.register("research", BaseAgent)

    AgentRegistry.register("research", _OtherAgent, overwrite=True)

    assert AgentRegistry.get("research") is _OtherAgent


def test_unregister_removes_a_registration():
    AgentRegistry.register("research", BaseAgent)

    AgentRegistry.unregister("research")

    assert AgentRegistry.get("research") is None


def test_unregister_an_unregistered_name_does_not_raise():
    AgentRegistry.unregister("missing")  # must not raise


def test_clear_removes_every_registration():
    AgentRegistry.register("a", BaseAgent)
    AgentRegistry.register("b", BaseAgent)

    AgentRegistry.clear()

    assert AgentRegistry.all_registered() == {}


def test_all_registered_returns_a_copy_not_a_live_view():
    AgentRegistry.register("research", BaseAgent)

    snapshot = AgentRegistry.all_registered()
    snapshot["extra"] = BaseAgent

    assert AgentRegistry.get("extra") is None
