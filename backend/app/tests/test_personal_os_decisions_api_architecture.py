"""P7.18 structural boundaries (§42): the governance surface uses only
authoritative flow methods for transitions, never mutates status
directly, keeps GET /decisions strictly read-only, introduces no new
Decision persistence, stays outside ExecutionRecord/AuditLog/external-
tools/scheduler, and reuses Personal OS's own existing daily-lifecycle
routes unmodified."""

import ast
import inspect

import main


def _route_module_source() -> str:
    import app.api.v1.routes.personal_os_decisions as route_module

    return inspect.getsource(route_module)


def _decisions_paths() -> list[str]:
    return [route.path for route in main.app.routes if "/personal-os/decisions" in getattr(route, "path", "") or "/personal-os/patterns" in getattr(route, "path", "") or "/personal-os/experiments" in getattr(route, "path", "") or "/personal-os/adaptations" in getattr(route, "path", "")]


def test_exactly_five_governance_routes_exist():
    assert set(_decisions_paths()) == {
        "/api/v1/personal-os/decisions",
        "/api/v1/personal-os/decisions/{entity_type}/{entity_id}",
        "/api/v1/personal-os/patterns/{pattern_id}/respond",
        "/api/v1/personal-os/experiments/{experiment_id}/respond",
        "/api/v1/personal-os/adaptations/{adaptation_id}/respond",
    }


def test_route_uses_authoritative_flow_methods_for_every_transition():
    source = _route_module_source()
    required_calls = (
        "flow.respond(", "flow.approve(", "flow.reject(", "flow.adopt(", "flow.rollback(", "flow.decide(",
    )
    for call in required_calls:
        assert call in source, f"personal_os_decisions.py never calls {call!r} - transitions must use authoritative flow methods"


def test_no_direct_status_mutation_from_the_route():
    """The API layer must never construct a Pattern/Experiment/Adaptation
    with a caller-chosen `status=` and save it directly - every status
    change must flow through an authoritative flow method instead. Only
    a `status=` keyword passed to one of the domain constructors
    themselves (Pattern/Experiment/Adaptation) would be a violation - the
    many `status=pattern.status.value`-shaped keywords elsewhere are
    read-only DTO field assignments, not mutations, and are excluded."""
    tree = ast.parse(_route_module_source())
    domain_constructors = {"Pattern", "Experiment", "Adaptation"}
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in domain_constructors:
            for kw in node.keywords:
                if kw.arg == "status":
                    violations.append(ast.dump(kw))
    assert violations == [], f"personal_os_decisions.py sets status= on a domain constructor directly: {violations}"

    forbidden_fragments = (".save(Pattern(", ".save(Experiment(", ".save(Adaptation(")
    source = _route_module_source()
    for fragment in forbidden_fragments:
        assert fragment not in source, f"personal_os_decisions.py constructs and saves {fragment!r} directly - all writes must go through a flow method"


def test_get_decisions_is_read_only():
    """GET /decisions must never call a mutating transition to manufacture
    its own list contents (§4/§29/§30)."""
    tree = ast.parse(_route_module_source())
    list_decisions_fn = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "list_decisions")
    body_source = ast.unparse(list_decisions_fn)

    forbidden_calls = ("surface_next(", "list_ready_for_review(", ".review(", "begin_evaluation(", ".decide(", ".approve(", ".reject(", ".adopt(", ".rollback(")
    for call in forbidden_calls:
        assert call not in body_source, f"list_decisions() calls {call!r} - GET /decisions must be strictly read-only"


def test_decision_detail_route_is_also_read_only():
    tree = ast.parse(_route_module_source())
    detail_fn = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "get_decision_detail")
    body_source = ast.unparse(detail_fn)

    forbidden_calls = ("surface_next(", "list_ready_for_review(", ".review(", "begin_evaluation(", ".decide(", ".approve(", ".reject(", ".adopt(", ".rollback(")
    for call in forbidden_calls:
        assert call not in body_source, f"get_decision_detail() calls {call!r} - detail retrieval must be strictly read-only"


def test_no_new_decision_persistence_exists():
    """Scoped to app/models/ and app/repositories/ specifically - the
    actual persistence layer where a new, competing Decision concept
    would appear (§32). Not scoped to all of app/, since an unrelated,
    pre-existing `Decision` class already exists in the Executive
    framework (app/services/ai/agents/executive/decision.py) - a real,
    legitimate, long-standing class with no relationship to Personal
    OS's own governance surface."""
    import pathlib

    app_dir = pathlib.Path(__file__).resolve().parents[1]
    for subdir in ("models", "repositories"):
        for path in (app_dir / subdir).rglob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name in ("Decision", "DecisionRecord", "DecisionRepository"):
                    raise AssertionError(f"Found forbidden new persistence class {node.name!r} in {path} - the decisions inbox must stay a derived read model")


def test_no_execution_record_or_audit_log_usage():
    source = _route_module_source()
    for fragment in ("ExecutionRecord", "AuditLog", "execution_record", "audit_log"):
        assert fragment not in source, f"personal_os_decisions.py references {fragment!r} - Personal OS's own versioned history is its own sufficient provenance"


def test_no_external_tool_or_agent_dispatch_is_reachable():
    tree = ast.parse(_route_module_source())
    imported = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    forbidden_fragments = ("tool_implementations", "agents.specialists.research", "ai.tools.manager", "ai.tools.execution", "ai.tools.permissions", "conversation_providers")
    for module in imported:
        for fragment in forbidden_fragments:
            assert fragment not in module, f"personal_os_decisions.py imports {module!r} - external tool/agent dispatch is out of scope for P7.18"


def test_no_scheduler_or_background_worker_introduced():
    source = _route_module_source()
    for fragment in ("celery", "Celery", "APScheduler", "BackgroundTasks", "cron", "asyncio.create_task", "redis", "Redis"):
        assert fragment not in source, f"personal_os_decisions.py references {fragment!r} - no automation/scheduling is in scope for P7.18"


def test_no_model_call_is_made_by_the_decisions_route():
    """§35: no new model call - existing narration already produced and
    persisted by the flows (review_narrative, hypothesis statements) is
    surfaced as-is; this route never constructs a RuntimeRequest or
    invokes RuntimeAdapter itself."""
    source = _route_module_source()
    for fragment in ("RuntimeAdapter(", "RuntimeRequest(", "PromptBuilder("):
        assert fragment not in source, f"personal_os_decisions.py references {fragment!r} - no new model call is in scope for P7.18"


def test_no_generic_workflow_or_state_machine_framework_introduced():
    source = _route_module_source()
    for fragment in ("class Workflow", "class StateMachine", "TRANSITIONS = {", "transition_table"):
        assert fragment not in source, f"personal_os_decisions.py contains {fragment!r} - a generic workflow engine is explicitly out of scope"


def test_existing_daily_lifecycle_routes_are_unaffected():
    daily_paths = {route.path for route in main.app.routes if getattr(route, "path", "").startswith("/api/v1/personal-os/today") or getattr(route, "path", "") == "/api/v1/personal-os/brief"}
    assert daily_paths == {
        "/api/v1/personal-os/today",
        "/api/v1/personal-os/today/intent",
        "/api/v1/personal-os/today/interact",
        "/api/v1/personal-os/today/reflect",
        "/api/v1/personal-os/brief",
    }
