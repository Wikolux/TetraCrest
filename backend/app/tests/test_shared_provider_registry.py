import threading

import pytest

from app.services.ai.shared.provider_registry import GenericProviderRegistry


class _RegistryA(GenericProviderRegistry):
    pass


class _RegistryB(GenericProviderRegistry):
    _registration_error = TypeError


def test_registry_starts_empty():
    assert _RegistryA.get("x") is None
    assert _RegistryA.all_registered() == {}


def test_register_and_get():
    _RegistryA.register("x", 1)

    assert _RegistryA.get("x") == 1
    assert _RegistryA.is_registered("x") is True


def test_registering_an_already_registered_key_raises_by_default():
    _RegistryA.register("x", 1)

    with pytest.raises(ValueError, match="already registered"):
        _RegistryA.register("x", 2)


def test_registering_with_overwrite_true_replaces_the_previous_registration():
    _RegistryA.register("x", 1)

    _RegistryA.register("x", 2, overwrite=True)

    assert _RegistryA.get("x") == 2


def test_unregister_removes_a_registration():
    _RegistryA.register("x", 1)

    _RegistryA.unregister("x")

    assert _RegistryA.get("x") is None


def test_unregister_an_unregistered_key_does_not_raise():
    _RegistryA.unregister("missing")


def test_clear_removes_every_registration():
    _RegistryA.register("a", 1)
    _RegistryA.register("b", 2)

    _RegistryA.clear()

    assert _RegistryA.all_registered() == {}


def test_all_registered_returns_a_copy_not_a_live_view():
    _RegistryA.register("x", 1)

    snapshot = _RegistryA.all_registered()
    snapshot["extra"] = 2

    assert _RegistryA.get("extra") is None


def test_custom_registration_error_is_used():
    with pytest.raises(TypeError):
        _RegistryB.register("x", 1)
        _RegistryB.register("x", 2)


def test_subclasses_never_share_storage():
    _RegistryA.register("shared-key", "from-a")

    assert _RegistryB.get("shared-key") is None


def test_a_third_independent_subclass_also_starts_empty():
    class _RegistryC(GenericProviderRegistry):
        pass

    _RegistryA.register("k", "a")
    _RegistryB.register("k", "b")

    assert _RegistryC.get("k") is None


def test_concurrent_registrations_of_distinct_keys_all_succeed():
    class _RegistryD(GenericProviderRegistry):
        pass

    errors = []

    def _register(index: int) -> None:
        try:
            _RegistryD.register(f"key-{index}", index)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_register, args=(i,)) for i in range(50)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(_RegistryD.all_registered()) == 50


@pytest.fixture(autouse=True)
def _isolate():
    yield
    _RegistryA.clear()
    _RegistryB.clear()
