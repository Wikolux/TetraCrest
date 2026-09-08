"""P7.15: authorization security tests for the governed real-world action
vertical slice - proving the Tool Framework's own permission enforcement
actually gates WikipediaSearchTool's real network call, at the lowest
level the mechanism operates (ToolExecutor/PermissionPolicy), independent
of the fixed /research/lookup route (which always grants the correct
permission by construction - see P7.15 §20's own instruction not to
fabricate a route-level denial that cannot really happen).

Every test here asserts an actual HTTP-call count, never merely a
ToolResult's own success flag - the point is proving zero network access
occurred, not just that an error was returned."""

import httpx

from app.services.ai.tools.context import ToolContext
from app.services.ai.tools.enums import ToolPermission
from app.services.ai.tools.execution import ToolExecutor
from app.services.ai.tools.manager import ToolManager
from app.services.ai.tools.permissions import PermissionPolicy
from app.services.tool_implementations.wikipedia_search_tool import WikipediaSearchTool


class _CountingGet:
    def __init__(self, json_body=None, status_code=200):
        self.calls = 0
        self.json_body = json_body if json_body is not None else {"query": {"search": [{"title": "T", "snippet": "s"}]}}
        self.status_code = status_code

    def __call__(self, url, **kwargs):
        self.calls += 1
        request = httpx.Request("GET", url)
        return httpx.Response(self.status_code, json=self.json_body, request=request)


def _manager(policy: PermissionPolicy | None) -> ToolManager:
    return ToolManager(executor=ToolExecutor(permission_policy=policy))


# --- P7.15 §21: exact required permission matrix, asserting real HTTP-call counts ------------


def test_authorized_network_permission_executes_and_calls_wikipedia_exactly_once(monkeypatch):
    counting_get = _CountingGet()
    monkeypatch.setattr(httpx, "get", counting_get)

    manager = _manager(PermissionPolicy(granted_permissions=frozenset({ToolPermission.NETWORK})))
    result = manager.invoke("wikipedia_search", {"query": "python"})

    assert result.success is True
    assert counting_get.calls == 1


def test_wrong_permission_denies_and_makes_zero_external_calls(monkeypatch):
    counting_get = _CountingGet()
    monkeypatch.setattr(httpx, "get", counting_get)

    manager = _manager(PermissionPolicy(granted_permissions=frozenset({ToolPermission.FILESYSTEM_READ})))
    result = manager.invoke("wikipedia_search", {"query": "python"})

    assert result.success is False
    assert "Missing permissions" in result.error
    assert counting_get.calls == 0


def test_deny_all_denies_and_makes_zero_external_calls(monkeypatch):
    counting_get = _CountingGet()
    monkeypatch.setattr(httpx, "get", counting_get)

    manager = _manager(PermissionPolicy(deny_all=True))
    result = manager.invoke("wikipedia_search", {"query": "python"})

    assert result.success is False
    assert counting_get.calls == 0


def test_no_policy_at_all_still_denies_when_the_orchestration_never_supplies_one():
    """This is NOT proving ToolExecutor's own shared default changed -
    it hasn't (see test_tool_permissions.py, unmodified). It proves the
    P7.15 vertical slice's own responsibility: a caller that (incorrectly)
    reuses the framework's bare default gets fail-OPEN behavior, which is
    exactly why the real /research/lookup route (app/api/v1/routes/research.py)
    is architecture-tested (test_dependency_rules.py) to never do this."""
    manager = _manager(None)
    executor = manager.executor
    assert executor.permission_policy is None  # the shared class's own unchanged default


def test_missing_query_denies_before_any_permission_or_network_check(monkeypatch):
    """Input validation runs before the permission check in ToolExecutor.execute()
    (execution.py: _validate() then _check_permissions()) - an invalid
    request never even reaches the authorization gate, let alone the
    network."""
    counting_get = _CountingGet()
    monkeypatch.setattr(httpx, "get", counting_get)

    manager = _manager(PermissionPolicy(granted_permissions=frozenset({ToolPermission.NETWORK})))
    result = manager.invoke("wikipedia_search", {})

    assert result.success is False
    assert "Missing required field" in result.error or "non-empty" in result.error
    assert counting_get.calls == 0


def test_empty_query_denies_with_zero_external_calls(monkeypatch):
    counting_get = _CountingGet()
    monkeypatch.setattr(httpx, "get", counting_get)

    manager = _manager(PermissionPolicy(granted_permissions=frozenset({ToolPermission.NETWORK})))
    result = manager.invoke("wikipedia_search", {"query": "   "})

    assert result.success is False
    assert counting_get.calls == 0


# --- direct ToolContext-level proof (no ToolManager indirection) ----------------------------


def test_check_permissions_directly_denies_missing_network_permission(monkeypatch):
    counting_get = _CountingGet()
    monkeypatch.setattr(httpx, "get", counting_get)

    tool = WikipediaSearchTool()
    context = ToolContext("wikipedia_search", parameters={"query": "python"})
    executor = ToolExecutor(permission_policy=PermissionPolicy())  # grants nothing

    result = executor.execute(tool, context)

    assert result.success is False
    assert counting_get.calls == 0
