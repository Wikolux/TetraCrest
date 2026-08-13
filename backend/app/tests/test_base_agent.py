import pytest

from app.services.ai.agents.base_agent import BaseAgent
from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentState
from app.services.ai.agents.state import AgentStateMachine
from app.services.ai.agents.types import AgentIdentity
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeResponse

_ALL_METHODS = (
    "initialize",
    "execute",
    "pause",
    "resume",
    "cancel",
    "shutdown",
    "health",
    "capabilities",
    "permissions",
    "memory",
    "planner",
    "runtime",
)


def _identity():
    return AgentIdentity(agent_id="agent-1", name="fake", display_name="Fake Agent")


def _stub(name):
    return {
        "initialize": lambda self: None,
        "execute": lambda self, context: RuntimeResponse(success=True),
        "pause": lambda self: None,
        "resume": lambda self: None,
        "cancel": lambda self: None,
        "shutdown": lambda self: None,
        "health": lambda self: True,
        "capabilities": lambda self: AgentCapabilities(),
        "permissions": lambda self: (),
        "memory": lambda self: None,
        "planner": lambda self: None,
        "runtime": lambda self: AIRuntime(),
    }[name]


def test_base_agent_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BaseAgent(_identity())


@pytest.mark.parametrize("missing_method", _ALL_METHODS)
def test_a_subclass_missing_any_one_method_cannot_be_instantiated(missing_method):
    namespace = {name: _stub(name) for name in _ALL_METHODS if name != missing_method}
    incomplete = type("IncompleteAgent", (BaseAgent,), namespace)

    with pytest.raises(TypeError):
        incomplete(_identity())


class _FakeAgent(BaseAgent):
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


def test_a_complete_subclass_can_be_instantiated():
    agent = _FakeAgent(_identity())

    assert isinstance(agent, BaseAgent)


def test_identity_is_wired_from_the_constructor():
    identity = _identity()

    agent = _FakeAgent(identity)

    assert agent.identity is identity


def test_default_state_machine_starts_at_created():
    agent = _FakeAgent(_identity())

    assert agent.state == AgentState.CREATED
    assert agent.state_machine.state == AgentState.CREATED


def test_a_custom_state_machine_can_be_injected():
    machine = AgentStateMachine(initial=AgentState.READY)

    agent = _FakeAgent(_identity(), state_machine=machine)

    assert agent.state_machine is machine
    assert agent.state == AgentState.READY


def test_runtime_accessor_returns_an_ai_runtime():
    agent = _FakeAgent(_identity())

    assert isinstance(agent.runtime(), AIRuntime)


def test_execute_returns_a_runtime_response():
    agent = _FakeAgent(_identity())

    response = agent.execute(AgentContext())

    assert isinstance(response, RuntimeResponse)
    assert response.success is True
