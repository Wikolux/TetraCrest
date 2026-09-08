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


def test_exactly_five_personal_os_routes_exist():
    paths = set(_personal_os_paths())
    assert paths == {
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
