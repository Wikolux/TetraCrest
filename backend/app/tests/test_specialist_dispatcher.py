import pytest

from app.services.ai.agents.specialists.dispatcher import SpecialistDispatcher
from app.services.ai.agents.specialists.registry import SpecialistRegistry
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType
from app.services.ai.agents.specialists.specialist_agent import SpecialistAgent


class _FakeSpecialist(SpecialistAgent):
    pass


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(SpecialistRegistry._providers)
    SpecialistRegistry._providers.clear()
    yield
    SpecialistRegistry._providers.clear()
    SpecialistRegistry._providers.update(original)


def test_dispatch_by_task_type_returns_none_when_nothing_registered():
    assert SpecialistDispatcher().dispatch_by_task_type(SpecialistTaskType.RESEARCH) is None


def test_dispatch_by_task_type_matches_a_registered_specialist():
    SpecialistRegistry.register(
        "research", _FakeSpecialist, specialization="research", supported_tasks={SpecialistTaskType.RESEARCH}
    )

    assert SpecialistDispatcher().dispatch_by_task_type(SpecialistTaskType.RESEARCH) == "research"


def test_dispatch_by_task_type_returns_none_when_no_specialist_supports_it():
    SpecialistRegistry.register(
        "research", _FakeSpecialist, specialization="research", supported_tasks={SpecialistTaskType.RESEARCH}
    )

    assert SpecialistDispatcher().dispatch_by_task_type(SpecialistTaskType.COMPARISON) is None


def test_dispatch_by_specialization_matches_a_registered_specialist():
    SpecialistRegistry.register("research", _FakeSpecialist, specialization="research")

    assert SpecialistDispatcher().dispatch_by_specialization("research") == "research"


def test_dispatch_by_specialization_returns_none_for_no_match():
    assert SpecialistDispatcher().dispatch_by_specialization("finance") is None


def test_adding_a_new_specialist_requires_no_dispatcher_code_change():
    # Open/Closed: SpecialistDispatcher's own code never changes -
    # registering a new specialist with the right supported_tasks is
    # enough for it to start being selected.
    dispatcher = SpecialistDispatcher()

    assert dispatcher.dispatch_by_task_type(SpecialistTaskType.COMPARISON) is None

    class _NewSpecialist(SpecialistAgent):
        pass

    SpecialistRegistry.register(
        "comparison-specialist",
        _NewSpecialist,
        specialization="comparison",
        supported_tasks={SpecialistTaskType.COMPARISON},
    )

    assert dispatcher.dispatch_by_task_type(SpecialistTaskType.COMPARISON) == "comparison-specialist"


def test_no_instantiation_is_needed_to_answer_a_dispatch_query():
    # _FakeSpecialist is never instantiable (SpecialistAgent is fully
    # abstract) - passing proves dispatch works purely off
    # registration-time metadata.
    SpecialistRegistry.register(
        "research", _FakeSpecialist, specialization="research", supported_tasks={SpecialistTaskType.RESEARCH}
    )

    assert SpecialistDispatcher().dispatch_by_task_type(SpecialistTaskType.RESEARCH) == "research"
