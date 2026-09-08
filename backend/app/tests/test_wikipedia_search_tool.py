"""WikipediaSearchTool (P7.15): request shape, response normalization,
error handling, and the domain-lock guarantee that no caller-supplied
query string can redirect this tool to another host - all deterministic,
no real network access."""

import httpx
import pytest

from app.services.ai.tools.context import ToolContext
from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.tool_implementations.wikipedia_search_tool import WIKIPEDIA_SEARCH_URL, WikipediaSearchTool


def _fake_get(json_body: dict, status_code: int = 200):
    def _get(url, **kwargs):
        request = httpx.Request("GET", url, params=kwargs.get("params"))
        return httpx.Response(status_code, json=json_body, request=request)

    return _get


def _fake_get_connection_error():
    def _get(url, **kwargs):
        raise httpx.ConnectError("Connection failed", request=httpx.Request("GET", url))

    return _get


def _fake_get_timeout():
    def _get(url, **kwargs):
        raise httpx.ReadTimeout("Read timed out", request=httpx.Request("GET", url))

    return _get


def _search_response(*results):
    return {"query": {"search": list(results)}}


def _context(query="python programming"):
    return ToolContext("wikipedia_search", parameters={"query": query})


# --- declared identity/metadata -------------------------------------------------------------


def test_tool_declares_search_category_and_network_permission():
    tool = WikipediaSearchTool()
    assert tool.tool_id == "wikipedia_search"
    assert tool.category == ToolCategory.SEARCH
    assert tool.permissions == frozenset({ToolPermission.NETWORK})
    assert ToolCapability.NETWORK in tool.capabilities
    assert ToolCapability.READ in tool.capabilities


def test_health_check_never_makes_a_real_request(monkeypatch):
    def _get(*args, **kwargs):
        raise AssertionError("health_check() must never make a real HTTP request")

    monkeypatch.setattr(httpx, "get", _get)
    assert WikipediaSearchTool().health_check() is True


# --- input validation: invalid input never reaches the network ------------------------------


def test_validate_rejects_missing_query():
    with pytest.raises(ValueError, match="non-empty"):
        WikipediaSearchTool().validate({})


def test_validate_rejects_empty_query():
    with pytest.raises(ValueError, match="non-empty"):
        WikipediaSearchTool().validate({"query": "   "})


def test_validate_rejects_non_string_query():
    with pytest.raises(ValueError, match="non-empty"):
        WikipediaSearchTool().validate({"query": 12345})


def test_validate_accepts_a_real_query():
    WikipediaSearchTool().validate({"query": "python programming"})  # must not raise


# --- successful lookup, including the honest zero-results case (P7.15 §11) ------------------


def test_execute_returns_a_summary_of_top_results(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "get",
        _fake_get(_search_response({"title": "Python (programming language)", "snippet": "Python is a <span class=\"searchmatch\">programming</span> language."})),
    )
    result = WikipediaSearchTool().execute(_context())

    assert result.success is True
    assert "Python (programming language)" in result.output
    assert "<span" not in result.output  # markup stripped
    assert result.structured_output["result_count"] == 1
    assert result.structured_output["query"] == "python programming"


def test_execute_distinguishes_zero_results_from_failure(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get(_search_response()))
    result = WikipediaSearchTool().execute(_context(query="asdkjqwoekjasd"))

    assert result.success is True  # a real, honest "nothing found" - never a failure
    assert result.output == "No Wikipedia results found."
    assert result.structured_output["result_count"] == 0


def test_execute_caps_at_max_results(monkeypatch):
    captured = {}

    def _get(url, **kwargs):
        captured["params"] = kwargs["params"]
        request = httpx.Request("GET", url)
        return httpx.Response(200, json=_search_response({"title": "A", "snippet": "a"}), request=request)

    monkeypatch.setattr(httpx, "get", _get)
    WikipediaSearchTool().execute(_context())

    assert captured["params"]["srlimit"] == 3


# --- error handling (P7.15 §12) --------------------------------------------------------------


def test_execute_handles_non_success_status(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get({}, status_code=503))
    result = WikipediaSearchTool().execute(_context())

    assert result.success is False
    assert "failed" in result.error.lower()


def test_execute_handles_connection_failure(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get_connection_error())
    result = WikipediaSearchTool().execute(_context())

    assert result.success is False
    assert "failed" in result.error.lower()


def test_execute_handles_timeout(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get_timeout())
    result = WikipediaSearchTool().execute(_context())

    assert result.success is False
    assert "timed out" in result.error.lower()


def test_execute_handles_malformed_json(monkeypatch):
    def _get(url, **kwargs):
        request = httpx.Request("GET", url)
        return httpx.Response(200, content=b"not json", request=request)

    monkeypatch.setattr(httpx, "get", _get)
    result = WikipediaSearchTool().execute(_context())

    assert result.success is False
    assert "malformed" in result.error.lower()


def test_execute_handles_unexpected_response_shape(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get({"unexpected": "shape"}))
    result = WikipediaSearchTool().execute(_context())

    assert result.success is False
    assert "malformed" in result.error.lower()


# --- domain-lock / SSRF protection (P7.15 §10) - the critical safety proof ------------------


@pytest.mark.parametrize(
    "malicious_query",
    [
        "http://evil.example.com/steal",
        "../../etc/passwd",
        "@evil.example.com",
        "wikipedia.org#@evil.example.com",
        "127.0.0.1:8080",
    ],
)
def test_no_query_string_can_redirect_the_request_to_another_host(monkeypatch, malicious_query):
    captured = {}

    def _get(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        request = httpx.Request("GET", url, params=kwargs.get("params"))
        return httpx.Response(200, json=_search_response(), request=request)

    monkeypatch.setattr(httpx, "get", _get)
    WikipediaSearchTool().execute(_context(query=malicious_query))

    # the URL passed to httpx.get is always the fixed constant - never
    # influenced by the query - and the malicious string only ever
    # appears as the value of the srsearch parameter
    assert captured["url"] == WIKIPEDIA_SEARCH_URL
    assert captured["url"] == "https://en.wikipedia.org/w/api.php"
    assert captured["params"]["srsearch"] == malicious_query


# --- architecture protections (P7.15 §27) -----------------------------------------------------


def test_research_agent_never_imports_the_concrete_wikipedia_tool():
    import ast
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "services" / "ai" / "agents" / "specialists" / "research" / "research_agent.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    violations = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.services.tool_implementations")
    ]
    assert violations == [], f"ResearchAgent must never import a concrete tool directly: {violations}"


def test_personal_os_never_imports_the_concrete_wikipedia_tool():
    import ast
    from pathlib import Path

    personal_os_dir = Path(__file__).resolve().parents[1] / "services" / "personal_os"
    violations = []
    for path in personal_os_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.services.tool_implementations"):
                violations.append(str(path))
    assert violations == [], f"Personal OS must never import a concrete tool directly: {violations}"


def test_research_route_never_constructs_bare_policy_less_defaults():
    """P7.15 §4/§27: the production research workflow must always inject
    a non-None PermissionPolicy - never ToolExecutor()/ToolManager()/
    ToolAdapter() with their bare, fail-open-by-default constructors."""
    import inspect

    import app.api.v1.routes.research as route_module

    source = inspect.getsource(route_module)
    assert "ToolExecutor()" not in source
    assert "ToolManager()" not in source
    assert "ToolAdapter()" not in source
    assert "permission_policy=" in source


def test_tool_executor_global_default_permission_policy_is_still_none():
    """P7.15 §4/§5: the SHARED framework class's own default must remain
    exactly as it was - this milestone fails closed by composition in the
    new route, never by tightening ToolExecutor itself, which would be a
    wider, unauthorized change to existing/other callers and tests."""
    from app.services.ai.tools.execution import ToolExecutor

    assert ToolExecutor().permission_policy is None


def test_no_provider_native_tool_call_representation_was_added():
    """P7.15 §14/§27: prompt -> model -> text only, still. No structured
    tool-call/function-call field exists anywhere in the provider-neutral
    contracts."""
    import inspect

    from app.services.ai.conversation import types as conversation_types
    from app.services.ai.runtime import types as runtime_types

    for module in (conversation_types, runtime_types):
        source = inspect.getsource(module)
        for forbidden in ("tool_call", "function_call", "tool_calls"):
            assert forbidden not in source, f"{module.__name__} contains {forbidden!r} - provider-native tool calling remains deferred"


def test_exactly_one_tool_executor_and_tool_registry_class_exist():
    """P7.15 §27 item 9: no second Tool Framework was introduced."""
    import ast

    from app.tests.architecture.dependency_rules import AI_ROOT_DIR

    matches = {"ToolExecutor": [], "ToolRegistry": []}
    for path in AI_ROOT_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in matches:
                matches[node.name].append(str(path))
    for class_name, paths in matches.items():
        assert len(paths) == 1, f"Expected exactly one {class_name} class, found: {paths}"
