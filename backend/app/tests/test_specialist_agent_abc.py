import pytest

from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.shared.context import SpecialistContext
from app.services.ai.agents.specialists.shared.response import SpecialistResponse
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType
from app.services.ai.agents.specialists.specialist_agent import SpecialistAgent
from app.services.ai.agents.types import AgentIdentity
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeResponse

_BASE_AGENT_MEMBERS = (
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
_SPECIALIST_MEMBERS = ("specialization", "supported_tasks", "plan", "evaluate", "self_check", "health_check")
_ALL_MEMBERS = _BASE_AGENT_MEMBERS + _SPECIALIST_MEMBERS


def _identity():
    return AgentIdentity(agent_id="fake-specialist", name="fake", display_name="Fake Specialist")


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
        "specialization": lambda self: "fake",
        "supported_tasks": lambda self: frozenset({SpecialistTaskType.RESEARCH}),
        "plan": lambda self, context: (),
        "evaluate": lambda self, response: True,
        "self_check": lambda self: True,
        "health_check": lambda self: True,
    }[name]


def test_specialist_agent_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        SpecialistAgent(_identity())


@pytest.mark.parametrize("missing_member", _ALL_MEMBERS)
def test_a_subclass_missing_any_required_member_cannot_be_instantiated(missing_member):
    namespace = {name: _stub(name) for name in _ALL_MEMBERS if name != missing_member}
    incomplete = type("IncompleteSpecialist", (SpecialistAgent,), namespace)

    with pytest.raises(TypeError):
        incomplete(_identity())


class _FakeSpecialist(SpecialistAgent):
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

    def specialization(self) -> str:
        return "fake"

    def supported_tasks(self) -> frozenset[SpecialistTaskType]:
        return frozenset({SpecialistTaskType.RESEARCH})

    def plan(self, context: SpecialistContext):
        return ()

    def evaluate(self, response: SpecialistResponse) -> bool:
        return True

    def self_check(self) -> bool:
        return True

    def health_check(self) -> bool:
        return True


def test_a_complete_subclass_can_be_instantiated_and_is_a_base_agent():
    from app.services.ai.agents.base_agent import BaseAgent

    specialist = _FakeSpecialist(_identity())

    assert isinstance(specialist, SpecialistAgent)
    assert isinstance(specialist, BaseAgent)


def test_specialist_specific_members_work():
    specialist = _FakeSpecialist(_identity())

    assert specialist.specialization() == "fake"
    assert specialist.supported_tasks() == {SpecialistTaskType.RESEARCH}
    assert specialist.evaluate(SpecialistResponse(success=True)) is True
    assert specialist.self_check() is True
    assert specialist.health_check() is True
