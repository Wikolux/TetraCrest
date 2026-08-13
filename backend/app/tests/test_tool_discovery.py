import pytest

from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.discovery import ToolDiscovery
from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.ai.tools.registry import ToolRegistry


class _FakeTool(BaseTool):
    pass


@pytest.fixture(autouse=True)
def _isolated_registry():
    original = dict(ToolRegistry._providers)
    ToolRegistry._providers.clear()
    yield
    ToolRegistry._providers.clear()
    ToolRegistry._providers.update(original)


@pytest.fixture(autouse=True)
def _seed_registry():
    ToolRegistry.register(
        "web-search",
        _FakeTool,
        name="Web Search",
        category=ToolCategory.SEARCH,
        capabilities={ToolCapability.SEARCH, ToolCapability.NETWORK},
        permissions={ToolPermission.NETWORK},
    )
    ToolRegistry.register(
        "email-sender",
        _FakeTool,
        name="Email Sender",
        category=ToolCategory.EMAIL,
        capabilities={ToolCapability.WRITE, ToolCapability.NETWORK},
        permissions={ToolPermission.EMAIL_SEND},
    )


def test_by_category_returns_matching_tool_ids():
    discovery = ToolDiscovery()

    assert discovery.by_category(ToolCategory.SEARCH) == ("web-search",)
    assert discovery.by_category(ToolCategory.EMAIL) == ("email-sender",)


def test_by_category_returns_empty_tuple_for_no_matches():
    assert ToolDiscovery().by_category(ToolCategory.SHELL) == ()


def test_by_capability_returns_matching_tool_ids():
    discovery = ToolDiscovery()

    assert discovery.by_capability(ToolCapability.SEARCH) == ("web-search",)
    assert set(discovery.by_capability(ToolCapability.NETWORK)) == {"web-search", "email-sender"}


def test_by_permission_returns_matching_tool_ids():
    discovery = ToolDiscovery()

    assert discovery.by_permission(ToolPermission.EMAIL_SEND) == ("email-sender",)


def test_by_name_returns_matching_tool_ids():
    discovery = ToolDiscovery()

    assert discovery.by_name("Web Search") == ("web-search",)


def test_by_name_returns_empty_tuple_for_no_match():
    assert ToolDiscovery().by_name("Nonexistent Tool") == ()


def test_by_tool_id_returns_the_id_when_registered():
    assert ToolDiscovery().by_tool_id("web-search") == "web-search"


def test_by_tool_id_returns_none_when_not_registered():
    assert ToolDiscovery().by_tool_id("missing") is None


def test_no_instantiation_is_needed_to_answer_a_discovery_query():
    # _FakeTool is never instantiable (BaseTool is fully abstract) - if
    # discovery ever tried to construct a candidate, this whole test file
    # would fail at fixture setup, not just this one test. Passing proves
    # discovery works purely off registration-time metadata.
    discovery = ToolDiscovery()

    assert discovery.by_category(ToolCategory.SEARCH) == ("web-search",)
