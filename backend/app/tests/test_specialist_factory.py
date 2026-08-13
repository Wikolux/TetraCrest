import pytest

from app.services.ai.agents.capabilities import AgentCapabilities
from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.specialists.factory import SpecialistFactory
from app.services.ai.agents.specialists.registry import SpecialistRegistry
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType
from app.services.ai.agents.specialists.specialist_agent import SpecialistAgent
from app.services.ai.agents.types import AgentError
from app.services.ai.runtime.runtime import AIRuntime
from app.services.ai.runtime.types import RuntimeResponse


class _FakeSpecialist(SpecialistAgent):
    def __init__(self, label="default"):
        self.label = label

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

    def plan(self, context):
        return ()

    def evaluate(self, response) -> bool:
        return True

    def self_check(self) -> bool:
        return True

    def health_check(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(SpecialistRegistry._providers)
    SpecialistRegistry._providers.clear()
    yield
    SpecialistRegistry._providers.clear()
    SpecialistRegistry._providers.update(original)


def test_create_raises_for_an_unknown_specialist():
    with pytest.raises(AgentError, match="Unknown specialist"):
        SpecialistFactory.create("research")


def test_create_constructs_the_registered_specialist_class():
    SpecialistRegistry.register("research", _FakeSpecialist, specialization="research")

    specialist = SpecialistFactory.create("research")

    assert isinstance(specialist, _FakeSpecialist)
    assert specialist.label == "default"


def test_create_forwards_constructor_arguments():
    SpecialistRegistry.register("research", _FakeSpecialist, specialization="research")

    specialist = SpecialistFactory.create("research", label="custom")

    assert specialist.label == "custom"


def test_exists_reflects_registry_state():
    assert SpecialistFactory.exists("research") is False

    SpecialistRegistry.register("research", _FakeSpecialist, specialization="research")

    assert SpecialistFactory.exists("research") is True


def test_available_lists_every_registered_specialist():
    SpecialistRegistry.register("a", _FakeSpecialist, specialization="a")
    SpecialistRegistry.register("b", _FakeSpecialist, specialization="b")

    assert set(SpecialistFactory.available()) == {"a", "b"}


def test_the_factory_never_needs_to_change_when_a_new_specialist_is_registered():
    class _AnotherSpecialist(_FakeSpecialist):
        pass

    SpecialistRegistry.register("another", _AnotherSpecialist, specialization="another")

    specialist = SpecialistFactory.create("another")

    assert isinstance(specialist, _AnotherSpecialist)
