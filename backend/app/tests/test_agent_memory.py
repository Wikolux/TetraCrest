import pytest

from app.services.ai.agents.memory import AgentMemory

_ALL_METHODS = ("remember", "retrieve", "forget", "search")


def test_agent_memory_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        AgentMemory()


def _stub(name):
    if name == "remember":
        return lambda self, item, **kwargs: None
    if name == "forget":
        return lambda self, item_id: None
    return lambda self, query, **kwargs: []


@pytest.mark.parametrize("missing_method", _ALL_METHODS)
def test_a_subclass_missing_any_one_method_cannot_be_instantiated(missing_method):
    namespace = {name: _stub(name) for name in _ALL_METHODS if name != missing_method}
    incomplete = type("IncompleteMemory", (AgentMemory,), namespace)

    with pytest.raises(TypeError):
        incomplete()


def test_a_subclass_implementing_every_method_can_be_instantiated():
    namespace = {name: _stub(name) for name in _ALL_METHODS}
    complete = type("CompleteMemory", (AgentMemory,), namespace)

    instance = complete()

    assert isinstance(instance, AgentMemory)
    instance.remember("fact")
    instance.forget("id-1")
    assert instance.retrieve("query") == []
    assert instance.search("query") == []
