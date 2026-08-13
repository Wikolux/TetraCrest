import threading

import pytest

from app.services.ai.shared.provider_registry import GenericProviderRegistry
from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.ai.tools.registry import ToolRegistration, ToolRegistry
from app.services.ai.tools.shared.exceptions import ToolError


def test_registry_is_built_on_the_generic_registry_not_a_parallel_type():
    assert issubclass(ToolRegistry, GenericProviderRegistry)


class _FakeTool(BaseTool):
    pass  # never instantiated in these tests - the registry stores classes


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(ToolRegistry._providers)
    ToolRegistry._providers.clear()
    yield
    ToolRegistry._providers.clear()
    ToolRegistry._providers.update(original)


def test_registry_starts_empty():
    assert ToolRegistry.get("search") is None
    assert ToolRegistry.available() == ()


def test_register_and_get():
    ToolRegistry.register(
        "search", _FakeTool, name="Search", category=ToolCategory.SEARCH, capabilities={ToolCapability.SEARCH}
    )

    assert ToolRegistry.get("search") is _FakeTool
    assert ToolRegistry.exists("search") is True


def test_registering_an_already_registered_tool_id_raises_by_default():
    ToolRegistry.register("search", _FakeTool, name="Search", category=ToolCategory.SEARCH)

    with pytest.raises(ToolError, match="already registered"):
        ToolRegistry.register("search", _FakeTool, name="Search", category=ToolCategory.SEARCH)


def test_registering_with_overwrite_true_replaces_the_previous_registration():
    class _OtherTool(BaseTool):
        pass

    ToolRegistry.register("search", _FakeTool, name="Search", category=ToolCategory.SEARCH)

    ToolRegistry.register("search", _OtherTool, name="Search v2", category=ToolCategory.SEARCH, overwrite=True)

    assert ToolRegistry.get("search") is _OtherTool


def test_unregister_removes_a_registration():
    ToolRegistry.register("search", _FakeTool, name="Search", category=ToolCategory.SEARCH)

    ToolRegistry.unregister("search")

    assert ToolRegistry.get("search") is None


def test_unregister_an_unregistered_tool_id_does_not_raise():
    ToolRegistry.unregister("missing")


def test_clear_removes_every_registration():
    ToolRegistry.register("a", _FakeTool, name="A", category=ToolCategory.SEARCH)
    ToolRegistry.register("b", _FakeTool, name="B", category=ToolCategory.EMAIL)

    ToolRegistry.clear()

    assert ToolRegistry.available() == ()


def test_available_lists_every_registered_tool_id():
    ToolRegistry.register("a", _FakeTool, name="A", category=ToolCategory.SEARCH)
    ToolRegistry.register("b", _FakeTool, name="B", category=ToolCategory.EMAIL)

    assert set(ToolRegistry.available()) == {"a", "b"}


def test_categories_aggregates_across_every_registered_tool():
    ToolRegistry.register("a", _FakeTool, name="A", category=ToolCategory.SEARCH)
    ToolRegistry.register("b", _FakeTool, name="B", category=ToolCategory.EMAIL)

    assert ToolRegistry.categories() == {ToolCategory.SEARCH, ToolCategory.EMAIL}


def test_capabilities_aggregates_across_every_registered_tool():
    ToolRegistry.register(
        "a", _FakeTool, name="A", category=ToolCategory.SEARCH, capabilities={ToolCapability.SEARCH}
    )
    ToolRegistry.register(
        "b", _FakeTool, name="B", category=ToolCategory.EMAIL, capabilities={ToolCapability.WRITE}
    )

    assert ToolRegistry.capabilities() == {ToolCapability.SEARCH, ToolCapability.WRITE}


def test_get_registration_returns_the_full_registration_record():
    ToolRegistry.register(
        "search",
        _FakeTool,
        name="Search",
        category=ToolCategory.SEARCH,
        capabilities={ToolCapability.SEARCH},
        permissions={ToolPermission.NETWORK},
    )

    registration = ToolRegistry.get_registration("search")

    assert isinstance(registration, ToolRegistration)
    assert registration.tool_class is _FakeTool
    assert registration.name == "Search"
    assert registration.category == ToolCategory.SEARCH
    assert registration.capabilities == {ToolCapability.SEARCH}
    assert registration.permissions == {ToolPermission.NETWORK}


def test_registration_capabilities_and_permissions_default_to_empty_frozensets():
    ToolRegistry.register("search", _FakeTool, name="Search", category=ToolCategory.SEARCH)

    registration = ToolRegistry.get_registration("search")

    assert registration.capabilities == frozenset()
    assert registration.permissions == frozenset()


def test_all_registrations_returns_a_copy_not_a_live_view():
    ToolRegistry.register("search", _FakeTool, name="Search", category=ToolCategory.SEARCH)

    snapshot = ToolRegistry.all_registrations()
    snapshot["extra"] = snapshot["search"]

    assert ToolRegistry.get("extra") is None


# --- thread safety ------------------------------------------------------------------------


def test_concurrent_registrations_of_distinct_tool_ids_all_succeed():
    errors = []

    def _register(index: int) -> None:
        try:
            ToolRegistry.register(f"tool-{index}", _FakeTool, name=f"Tool {index}", category=ToolCategory.SEARCH)
        except Exception as exc:  # noqa: BLE001 - captured for the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=_register, args=(i,)) for i in range(50)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(ToolRegistry.available()) == 50
