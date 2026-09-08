"""P7.16 architecture protections: ExecutionRecord stays a distinct
responsibility from AuditLog, the route commits STARTED before any
external call (source-order defense in depth, behaviorally proven
separately in test_research_lookup_route.py), the same root
SharedExecutionContext reaches both the ledger and the specialist
execution, AuditLog carries the same execution/correlation identity, no
idempotency/recovery machinery was introduced, Personal OS stays
decoupled, and no second execution framework exists."""

import ast
import inspect
from pathlib import Path


def _route_source() -> str:
    import app.api.v1.routes.research as route_module

    return inspect.getsource(route_module)


# --- distinct responsibility from AuditLog (P7.16 §33 item 1) --------------------------------


def test_execution_record_is_a_distinct_model_from_audit_log():
    from app.models.audit_log import AuditLog
    from app.models.execution_record import ExecutionRecord

    assert ExecutionRecord is not AuditLog
    assert ExecutionRecord.__tablename__ != AuditLog.__tablename__
    assert not issubclass(ExecutionRecord, AuditLog)
    assert not issubclass(AuditLog, ExecutionRecord)


def test_audit_log_repository_gained_no_lifecycle_methods():
    """AuditLog was not turned into the ledger - it still only has the
    plain BaseRepository surface (create/get_by_id/update/delete/...),
    no mark_succeeded/mark_failed/create_started-style additions."""
    from app.repositories.audit_log_repository import AuditLogRepository

    forbidden = ("mark_succeeded", "mark_failed", "create_started", "list_non_terminal")
    for name in forbidden:
        assert not hasattr(AuditLogRepository, name), f"AuditLogRepository gained {name!r} - AuditLog must not become the execution ledger"


# --- STARTED committed before any external call (source-order defense in depth) --------------


def test_route_source_creates_the_started_record_before_calling_research():
    source = _route_source()
    started_index = source.index("execution_repo.create_started(")
    research_index = source.index("agent.research(")
    assert started_index < research_index, "create_started() must appear before agent.research() in the route source"


# --- one root SharedExecutionContext, shared by the ledger and the specialist execution -------


def test_route_constructs_exactly_one_shared_execution_context():
    tree = ast.parse(_route_source())
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "SharedExecutionContext"
    ]
    assert len(calls) == 1, "the route must construct exactly one root SharedExecutionContext (E0)"


def test_route_uses_the_same_shared_context_for_the_ledger_and_the_agent_context():
    source = _route_source()
    assert "execution_id=shared.execution_id" in source
    assert "AgentContext(shared=shared)" in source


# --- AuditLog references the same execution/correlation identity (P7.16 §18) -----------------


def test_record_audit_carries_execution_and_correlation_identity():
    source = _route_source()
    assert "execution_id: str" in source or "execution_id=execution_id" in source
    assert '"execution_id": execution_id' in source
    assert '"correlation_id": correlation_id' in source


# --- no idempotency/recovery machinery introduced (P7.16 §22/§25) ----------------------------


def test_no_idempotency_or_recovery_machinery_was_introduced():
    import app.models.execution_record as model_module
    import app.repositories.execution_record_repository as repo_module

    # "reconcil" deliberately excluded - both modules' own docstrings
    # correctly and honestly explain that they do NOT reconcile anything,
    # which legitimately uses the word.
    forbidden = ("idempoten", "dedup", "replay_protection", "scheduler", "celery", "background_worker")
    for module in (model_module, repo_module):
        source = inspect.getsource(module).lower()
        for fragment in forbidden:
            assert fragment not in source, f"{module.__name__} contains {fragment!r} - P7.16 explicitly defers this"


def test_list_non_terminal_does_not_itself_trigger_any_recovery_action():
    """list_non_terminal() must be a pure read - it exists only to make
    non-terminal records discoverable later, never to act on them."""
    import app.repositories.execution_record_repository as repo_module

    source = inspect.getsource(repo_module.ExecutionRecordRepository.list_non_terminal)
    assert ".query(" in source
    for forbidden in ("mark_succeeded", "mark_failed", "retry", "requeue"):
        assert forbidden not in source


# --- Personal OS remains decoupled (P7.16 §28) ------------------------------------------------


def test_personal_os_never_imports_execution_record():
    personal_os_dir = Path(__file__).resolve().parents[1] / "services" / "personal_os"
    violations = []
    for path in personal_os_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and (
                node.module.startswith("app.models.execution_record") or node.module.startswith("app.repositories.execution_record_repository")
            ):
                violations.append(str(path))
    assert violations == [], f"Personal OS must not depend on ExecutionRecord: {violations}"


# --- no second execution framework (P7.16 §33 item 9) -----------------------------------------


def test_exactly_one_execution_record_class_and_repository_exist():
    app_dir = Path(__file__).resolve().parents[1]
    matches = {"ExecutionRecord": [], "ExecutionRecordRepository": []}
    for path in app_dir.rglob("*.py"):
        if "/tests/" in str(path):
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in matches:
                matches[node.name].append(str(path))
    for class_name, paths in matches.items():
        assert len(paths) == 1, f"Expected exactly one {class_name} class, found: {paths}"
