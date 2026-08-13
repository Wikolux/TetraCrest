import pytest

from app.services.ai.agents.orchestrator import AgentOrchestrator

_ALL_METHODS = ("dispatch", "delegate", "synchronize", "terminate")


def test_agent_orchestrator_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        AgentOrchestrator()


def _stub(name):
    return {
        "dispatch": lambda self, agent, context: None,
        "delegate": lambda self, from_agent, to_agent, message: None,
        "synchronize": lambda self, agents: None,
        "terminate": lambda self, agent: None,
    }[name]


@pytest.mark.parametrize("missing_method", _ALL_METHODS)
def test_a_subclass_missing_any_one_method_cannot_be_instantiated(missing_method):
    namespace = {name: _stub(name) for name in _ALL_METHODS if name != missing_method}
    incomplete = type("IncompleteOrchestrator", (AgentOrchestrator,), namespace)

    with pytest.raises(TypeError):
        incomplete()


def test_a_subclass_implementing_every_method_can_be_instantiated():
    namespace = {name: _stub(name) for name in _ALL_METHODS}
    complete = type("CompleteOrchestrator", (AgentOrchestrator,), namespace)

    orchestrator = complete()

    assert isinstance(orchestrator, AgentOrchestrator)
    assert orchestrator.dispatch(None, None) is None
    assert orchestrator.delegate(None, None, None) is None
    assert orchestrator.synchronize(()) is None
    assert orchestrator.terminate(None) is None
