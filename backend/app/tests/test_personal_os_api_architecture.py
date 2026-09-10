"""P7.17 structural boundaries: the Personal OS API surface stays a thin
composition of existing flows, never duplicates business logic, never
reaches for the write-tool/external-tool stack, never uses ExecutionRecord
or writes AuditLog, and never exposes a generic chat or a Pattern/
Experiment/Adaptation decision endpoint - all explicitly out of this
milestone's scope per the P7.17 Phase 0 audit."""

import ast
import inspect

import main


def _route_module_source() -> str:
    import app.api.v1.routes.personal_os as route_module

    return inspect.getsource(route_module)


def _personal_os_paths() -> list[str]:
    return [route.path for route in main.app.routes if getattr(route, "path", "").startswith("/api/v1/personal-os")]


def test_exactly_five_daily_lifecycle_routes_exist():
    """Scoped to the daily-lifecycle surface P7.17 itself introduced -
    P7.18 later added a sibling governance surface (decisions/patterns/
    experiments/adaptations) under the same /personal-os prefix, which
    is a separate, additional route module (personal_os_decisions.py),
    not a change to this one; see
    test_personal_os_decisions_api_architecture.py's own
    test_existing_daily_lifecycle_routes_are_unaffected for the
    P7.18-side proof that these five are untouched."""
    daily_lifecycle_paths = {path for path in _personal_os_paths() if path.startswith("/api/v1/personal-os/today") or path == "/api/v1/personal-os/brief"}
    assert daily_lifecycle_paths == {
        "/api/v1/personal-os/today",
        "/api/v1/personal-os/today/intent",
        "/api/v1/personal-os/today/interact",
        "/api/v1/personal-os/today/reflect",
        "/api/v1/personal-os/brief",
    }


def test_no_generic_chat_endpoint_exists():
    forbidden_fragments = ("chat", "assistant", "/agent/")
    for path in _personal_os_paths():
        for fragment in forbidden_fragments:
            assert fragment not in path, f"{path} looks like a generic chat/assistant endpoint - forbidden in P7.17"


def test_no_pattern_experiment_adaptation_decision_endpoint_exists():
    source = _route_module_source()
    forbidden_fragments = (
        "pattern_flow.respond(",
        "pattern_flow.attach_recommendation(",
        "experiment_flow.approve(",
        "experiment_flow.decide(",
        "adaptation_flow.approve(",
        "adaptation_flow.adopt(",
        "adaptation_flow.rollback(",
        "adaptation_flow.reject(",
        "adaptation_flow.retire(",
    )
    for fragment in forbidden_fragments:
        assert fragment not in source, f"personal_os.py calls {fragment!r} - decision endpoints are out of scope for P7.17"


def test_no_mission_or_life_domain_crud_endpoint_exists():
    """Missions are only ever constructed as a read-only collaborator of
    PriorityIntelligenceFlow (via _build_priority_flow) - no route
    directly saves/creates/updates a Mission or LifeDomainState."""
    source = _route_module_source()
    forbidden_fragments = (
        "MissionRepository(db).save(",
        "LifeDomainStateRepository(db).save(",
        "@router.post(\"/missions",
        "@router.post(\"/life-domains",
        "@router.put(\"/missions",
        "@router.patch(\"/missions",
    )
    for fragment in forbidden_fragments:
        assert fragment not in source, f"personal_os.py contains {fragment!r} - Mission/LifeDomain CRUD is out of scope for P7.17"


def test_no_external_tool_or_agent_dispatch_is_reachable():
    tree = ast.parse(_route_module_source())
    imported = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    forbidden_fragments = (
        "tool_implementations",
        "agents.specialists.research",
        "ai.tools.manager",
        "ai.tools.execution",
        "ai.tools.permissions",
        "ai.agents.specialists.tool_adapter",
    )
    for module in imported:
        for fragment in forbidden_fragments:
            assert fragment not in module, f"personal_os.py imports {module!r} - external tool/agent dispatch is out of scope for P7.17"


def test_no_execution_record_or_audit_log_usage():
    source = _route_module_source()
    forbidden_fragments = ("ExecutionRecord", "AuditLog", "execution_record", "audit_log")
    for fragment in forbidden_fragments:
        assert fragment not in source, f"personal_os.py references {fragment!r} - Personal OS's own durable state is its own sufficient provenance (P7.17 Phase 0 §21-22)"


def test_route_only_constructs_sql_backed_repositories():
    """Production route code must never fall back to an in-memory
    repository - every repository constructed in personal_os.py must be
    one of the Sql* variants."""
    source = _route_module_source()
    assert "InMemory" not in source, "personal_os.py must only construct Sql*-backed repositories in production route code"


def test_route_reuses_existing_flows_and_defines_no_new_ranking_or_interpretation_logic():
    source = _route_module_source()
    forbidden_fragments = (
        "def calculate_score",
        "def rank_candidates",
        "def reconstruct(",
        "class DayInteractionInterpreter",
        "class HeuristicDayInteractionInterpreter",
        "def interpret(",
    )
    for fragment in forbidden_fragments:
        assert fragment not in source, f"personal_os.py defines {fragment!r} - all ranking/replanning/interpretation logic must remain in the existing flows"

    # confirms actual composition, not just absence of duplication
    assert "MorningInteractionFlow(" in source
    assert "EveningReflectionFlow(" in source
    assert "PriorityIntelligenceFlow(" in source
    assert "LivingDayFlow(" in source
    assert "PersonalStateReader(" in source
    assert "IntelligenceBriefBuilder(" in source


def test_current_day_is_resolved_through_one_seam_never_scattered_date_today_calls():
    source = _route_module_source()
    assert "resolve_personal_os_today(" in source
    assert "date.today()" not in source
    assert "datetime.now()" not in source


def test_no_client_supplied_date_reaches_a_mutating_flow_call():
    """Every call into a flow's own `today=` keyword must come from the
    one resolver, never from `payload.` (the request body)."""
    tree = ast.parse(_route_module_source())
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "today":
            if isinstance(node.value, ast.Attribute) and isinstance(node.value.value, ast.Name) and node.value.value.id == "payload":
                violations.append(ast.dump(node))
    assert violations == [], f"a flow call received today= from the request body: {violations}"


# --- P7.19: Daily Intent Activity Capture protections -------------------------------------------


def test_p719_introduces_no_new_endpoint():
    """P7.19 only extends the existing POST /today/intent request shape -
    it must not add a sixth Personal OS daily-lifecycle route."""
    daily_lifecycle_paths = {path for path in _personal_os_paths() if path.startswith("/api/v1/personal-os/today") or path == "/api/v1/personal-os/brief"}
    assert daily_lifecycle_paths == {
        "/api/v1/personal-os/today",
        "/api/v1/personal-os/today/intent",
        "/api/v1/personal-os/today/interact",
        "/api/v1/personal-os/today/reflect",
        "/api/v1/personal-os/brief",
    }


def test_p719_introduces_no_pattern_detection_or_surfacing_production_caller():
    source = _route_module_source()
    for fragment in ("PatternDetectionFlow", ".detect(", ".surface_next(", "pattern_flow"):
        assert fragment not in source, f"personal_os.py references {fragment!r} - P7.19 fixes evidence input only, never triggers detection"


def test_p719_introduces_no_orchestrator():
    """"Orchestrates"/"orchestration" is common, legitimate prose already
    used throughout Personal OS's own pre-existing docstrings (e.g.
    pattern_flow.py's own module docstring, unrelated to P7.19) - this
    checks specifically for an actual new orchestrator CLASS, not the
    English word."""
    import pathlib

    app_dir = pathlib.Path(__file__).resolve().parents[1]
    personal_os_paths = list((app_dir / "services" / "personal_os").rglob("*.py")) + [
        app_dir / "api" / "v1" / "routes" / "personal_os.py",
        app_dir / "api" / "v1" / "routes" / "personal_os_decisions.py",
    ]
    for path in personal_os_paths:
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and "orchestrat" in node.name.lower():
                raise AssertionError(f"{path} defines {node.name!r} - no orchestrator class is in scope for P7.19")


def test_p719_introduces_no_scheduler_or_background_worker():
    source = _route_module_source()
    for fragment in ("celery", "Celery", "APScheduler", "BackgroundTasks", "cron", "asyncio.create_task", "redis", "Redis"):
        assert fragment not in source, f"personal_os.py references {fragment!r} - no automation is in scope for P7.19"


def test_p719_introduces_no_external_tool():
    tree = ast.parse(_route_module_source())
    imported = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    forbidden_fragments = ("tool_implementations", "agents.specialists.research", "ai.tools.manager", "ai.tools.execution", "ai.tools.permissions")
    for module in imported:
        for fragment in forbidden_fragments:
            assert fragment not in module, f"personal_os.py imports {module!r} - external tools are out of scope for P7.19"


def test_p719_introduces_no_new_model_call():
    """Structured planned_activities are explicit user data - the model
    is never asked to infer activities from free text. personal_os.py
    itself never constructs a Runtime call directly (that seam belongs
    entirely to the flows, unchanged by P7.19)."""
    source = _route_module_source()
    assert "RuntimeRequest(" not in source
    assert "RuntimeAdapter(" not in source


def test_p719_dayevents_remain_separate_from_dailyintent():
    """Morning planned activities live on DailyIntent; midday changes
    live on DayEvent/Living Day - P7.19 must not collapse these. The
    interact() route function must never reference planned_activities."""
    tree = ast.parse(_route_module_source())
    interact_fn = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "interact")
    assert "planned_activities" not in ast.unparse(interact_fn)


def test_p719_get_routes_remain_non_mutating():
    """Re-confirms P7.17's own read-purity guarantee still holds after
    the P7.19 schema/flow change - GET /today and GET /brief construct
    no domain object with a caller-chosen status and call no `.save(`
    other than through an existing, already-covered flow method."""
    source = _route_module_source()
    get_today_fn = next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef) and node.name == "get_today")
    get_brief_fn = next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef) and node.name == "get_brief")
    for fn in (get_today_fn, get_brief_fn):
        body_source = ast.unparse(fn)
        assert ".save(" not in body_source, f"{fn.name}() writes state - GET must remain read-only"


def test_p719_does_not_touch_the_governance_route_module():
    """P7.18's governance surface (personal_os_decisions.py) must be
    byte-for-byte unaffected by P7.19."""
    import inspect

    import app.api.v1.routes.personal_os_decisions as decisions_route_module

    source = inspect.getsource(decisions_route_module)
    assert "explicit_planned_activities" not in source
    assert "PlannedActivityInput" not in source
