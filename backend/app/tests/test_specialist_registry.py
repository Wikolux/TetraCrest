import threading

import pytest

from app.services.ai.agents.specialists.registry import SpecialistRegistration, SpecialistRegistry
from app.services.ai.agents.specialists.shared.task import SpecialistTaskType
from app.services.ai.agents.specialists.specialist_agent import SpecialistAgent
from app.services.ai.agents.types import AgentError
from app.services.ai.shared.provider_registry import GenericProviderRegistry


def test_registry_is_built_on_the_generic_registry_not_a_parallel_type():
    assert issubclass(SpecialistRegistry, GenericProviderRegistry)


class _FakeSpecialist(SpecialistAgent):
    pass  # never instantiated - the registry stores classes


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(SpecialistRegistry._providers)
    SpecialistRegistry._providers.clear()
    yield
    SpecialistRegistry._providers.clear()
    SpecialistRegistry._providers.update(original)


def test_registry_starts_empty():
    assert SpecialistRegistry.get("research") is None
    assert SpecialistRegistry.available() == ()


def test_register_and_get():
    SpecialistRegistry.register(
        "research", _FakeSpecialist, specialization="research", supported_tasks={SpecialistTaskType.RESEARCH}
    )

    assert SpecialistRegistry.get("research") is _FakeSpecialist
    assert SpecialistRegistry.exists("research") is True


def test_registering_an_already_registered_name_raises_by_default():
    SpecialistRegistry.register("research", _FakeSpecialist, specialization="research")

    with pytest.raises(AgentError, match="already registered"):
        SpecialistRegistry.register("research", _FakeSpecialist, specialization="research")


def test_registering_with_overwrite_true_replaces_the_previous_registration():
    class _OtherSpecialist(SpecialistAgent):
        pass

    SpecialistRegistry.register("research", _FakeSpecialist, specialization="research")

    SpecialistRegistry.register("research", _OtherSpecialist, specialization="research-v2", overwrite=True)

    assert SpecialistRegistry.get("research") is _OtherSpecialist


def test_unregister_removes_a_registration():
    SpecialistRegistry.register("research", _FakeSpecialist, specialization="research")

    SpecialistRegistry.unregister("research")

    assert SpecialistRegistry.get("research") is None


def test_unregister_an_unregistered_name_does_not_raise():
    SpecialistRegistry.unregister("missing")


def test_clear_removes_every_registration():
    SpecialistRegistry.register("a", _FakeSpecialist, specialization="a")
    SpecialistRegistry.register("b", _FakeSpecialist, specialization="b")

    SpecialistRegistry.clear()

    assert SpecialistRegistry.available() == ()


def test_available_lists_every_registered_name():
    SpecialistRegistry.register("a", _FakeSpecialist, specialization="a")
    SpecialistRegistry.register("b", _FakeSpecialist, specialization="b")

    assert set(SpecialistRegistry.available()) == {"a", "b"}


def test_specializations_aggregates_across_every_registered_specialist():
    SpecialistRegistry.register("a", _FakeSpecialist, specialization="research")
    SpecialistRegistry.register("b", _FakeSpecialist, specialization="finance")

    assert SpecialistRegistry.specializations() == {"research", "finance"}


def test_get_registration_returns_the_full_registration_record():
    SpecialistRegistry.register(
        "research",
        _FakeSpecialist,
        specialization="research",
        supported_tasks={SpecialistTaskType.RESEARCH, SpecialistTaskType.ANALYSIS},
    )

    registration = SpecialistRegistry.get_registration("research")

    assert isinstance(registration, SpecialistRegistration)
    assert registration.specialist_class is _FakeSpecialist
    assert registration.specialization == "research"
    assert registration.supported_tasks == {SpecialistTaskType.RESEARCH, SpecialistTaskType.ANALYSIS}


def test_registration_supported_tasks_defaults_to_an_empty_frozenset():
    SpecialistRegistry.register("research", _FakeSpecialist, specialization="research")

    assert SpecialistRegistry.get_registration("research").supported_tasks == frozenset()


def test_all_registrations_returns_a_copy_not_a_live_view():
    SpecialistRegistry.register("research", _FakeSpecialist, specialization="research")

    snapshot = SpecialistRegistry.all_registrations()
    snapshot["extra"] = snapshot["research"]

    assert SpecialistRegistry.get("extra") is None


def test_concurrent_registrations_of_distinct_names_all_succeed():
    errors = []

    def _register(index: int) -> None:
        try:
            SpecialistRegistry.register(f"specialist-{index}", _FakeSpecialist, specialization=f"spec-{index}")
        except Exception as exc:  # noqa: BLE001 - captured for the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=_register, args=(i,)) for i in range(50)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(SpecialistRegistry.available()) == 50
