"""Structural enforcement for Personal OS's own Application-layer
boundary - the same AST-based technique
app/tests/architecture/dependency_rules.py already uses for
app/services/ai/, applied here since Personal OS lives at
app/services/personal_os/ (outside that scanner's own root, per its own
docstring: "every module under app/services/ai/") and therefore needs
its own, equivalent proof rather than inheriting the platform's.

Verifies, pack-wide, everything §16/§18 of the build spec name:
- Personal OS never imports a CP-01/CP-02 specialist class directly
  (§11, §12's own boundary rule; VERSION_1_PLATFORM_BASELINE.md's
  "Applications never import a Capability Pack's specialist code
  directly").
- Personal OS never constructs AIRuntime/AIMemoryService/a
  ConversationProvider directly - only through RuntimeAdapter/
  AgentMemory, the same seam every specialist already depends on.
- Personal OS registers no SpecialistAgent, declares no
  AgentCapability, and mints no new Memory Framework memory_type -
  evidence for (not proof of) "Personal OS is an Application, not a
  Capability Pack" (§18's own stop-condition question).
"""

import ast
import importlib
import inspect
from pathlib import Path

_PERSONAL_OS_MODULES = (
    "app.services.personal_os.shared.types",
    "app.services.personal_os.daily_intent",
    "app.services.personal_os.personal_state",
    "app.services.personal_os.reconciliation",
    "app.services.personal_os.reasoning",
    "app.services.personal_os.planning",
    "app.services.personal_os.repository",
    "app.services.personal_os.brief",
    "app.services.personal_os.evening",
    "app.services.personal_os.morning_flow",
    "app.services.personal_os.evening_flow",
    "app.services.personal_os.sql_repository",
    "app.services.personal_os.pattern",
    "app.services.personal_os.pattern_evidence",
    "app.services.personal_os.pattern_detectors",
    "app.services.personal_os.pattern_repository",
    "app.services.personal_os.pattern_flow",
    "app.services.personal_os.experiment",
    "app.services.personal_os.experiment_measurement",
    "app.services.personal_os.experiment_repository",
    "app.services.personal_os.experiment_flow",
)

_FORBIDDEN_SPECIALIST_FRAGMENTS = (
    "agents.specialists.personal_intelligence",
    "agents.specialists.product_management",
    "agents.specialists.research",
)


def _imported_modules(module_path: str) -> list[str]:
    module = importlib.import_module(module_path)
    tree = ast.parse(inspect.getsource(module))
    return [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]


def test_personal_os_never_imports_a_capability_pack_specialist_directly():
    violations = []
    for module_path in _PERSONAL_OS_MODULES:
        imported = _imported_modules(module_path)
        for fragment in _FORBIDDEN_SPECIALIST_FRAGMENTS:
            if any(fragment in name for name in imported):
                violations.append(f"{module_path} imports {fragment}")
    assert violations == []


def test_personal_os_never_constructs_airuntime_or_aimemoryservice_directly():
    violations = []
    for module_path in _PERSONAL_OS_MODULES:
        source = inspect.getsource(importlib.import_module(module_path))
        if "AIRuntime(" in source:
            violations.append(f"{module_path} constructs AIRuntime() directly")
        if "AIMemoryService(" in source:
            violations.append(f"{module_path} constructs AIMemoryService() directly")
        if "ConversationProviderFactory" in source or "ConversationProviderRegistry" in source:
            violations.append(f"{module_path} touches a ConversationProvider factory/registry directly")
    assert violations == []


def test_morning_flow_only_reaches_the_runtime_through_runtime_adapter():
    imported = _imported_modules("app.services.personal_os.morning_flow")
    assert any(name == "app.services.ai.agents.specialists.runtime_adapter" for name in imported)
    assert not any(name == "app.services.ai.runtime.runtime" for name in imported)


def test_personal_state_only_reaches_memory_through_agent_memory_contract():
    imported = _imported_modules("app.services.personal_os.personal_state")
    assert any(name == "app.services.ai.agents.memory" for name in imported)
    # Never the concrete retrieval/write-path services directly - only via
    # MemoryAdapter, the same seam every specialist depends on.
    assert not any(name == "app.services.retrieval.memory_retrieval_pipeline" for name in imported)
    assert not any(name == "app.services.ai_memory_service" for name in imported)


def test_personal_os_registers_no_specialist_agent():
    """Evidence for, not proof of, the Application-vs-Capability-Pack
    boundary question (§18): Personal OS never calls SpecialistRegistry/
    AgentRegistry.register(), and declares no AgentCapability - if it
    ever needs to, that is exactly the "should this actually be a
    Capability Pack" stop condition, not an ordinary implementation
    decision."""
    violations = []
    for module_path in _PERSONAL_OS_MODULES:
        source = inspect.getsource(importlib.import_module(module_path))
        if "SpecialistRegistry.register" in source or "AgentRegistry.register" in source:
            violations.append(f"{module_path} registers a specialist/agent")
        if "AgentCapability." in source:
            violations.append(f"{module_path} declares an AgentCapability")
    assert violations == []


def test_personal_os_mints_no_new_memory_framework_namespace():
    """Personal OS's own persistence (repository.py, sql_repository.py)
    never calls AgentMemory.remember() - it is not a Memory Framework
    writer at all, consistent with the Application Layer Definition's
    "not a new memory category" rule. This holds for the durable (P2)
    implementation exactly as it held for the in-memory (P1) one -
    switching storage medium never became a reason to reach for
    AgentMemory instead."""
    for module_path in (
        "app.services.personal_os.repository",
        "app.services.personal_os.sql_repository",
        "app.services.personal_os.pattern_repository",
        "app.services.personal_os.experiment_repository",
    ):
        source = inspect.getsource(importlib.import_module(module_path))
        assert ".remember(" not in source, f"{module_path} calls .remember() - unexpected AgentMemory write"


def test_sql_repository_uses_the_projects_own_repository_pattern_not_a_new_orm():
    """P2 §14: the durable implementation reuses the project's own
    BaseRepository-based repositories (app/repositories/) for all actual
    querying - it never runs a raw db.query() itself, and never
    introduces a second persistence framework."""
    source = inspect.getsource(importlib.import_module("app.services.personal_os.sql_repository"))
    assert "DailyIntentRecordRepository" in source
    assert "EveningReflectionRecordRepository" in source
    assert "db.query(" not in source


def test_evening_flow_only_reaches_the_runtime_through_runtime_adapter():
    imported = _imported_modules("app.services.personal_os.evening_flow")
    assert any(name == "app.services.ai.agents.specialists.runtime_adapter" for name in imported)
    assert not any(name == "app.services.ai.runtime.runtime" for name in imported)


def test_pattern_flow_only_reaches_the_runtime_through_runtime_adapter():
    """P3 §11's own narration step must follow morning_flow.py's/
    evening_flow.py's exact same seam - no second, ad hoc Runtime
    invocation path introduced just for pattern surfacing."""
    imported = _imported_modules("app.services.personal_os.pattern_flow")
    assert any(name == "app.services.ai.agents.specialists.runtime_adapter" for name in imported)
    assert not any(name == "app.services.ai.runtime.runtime" for name in imported)


def test_pattern_detectors_and_evidence_reader_do_not_touch_the_runtime():
    """P3 §18: detection and evidence-gathering must stay deterministic -
    neither module may import RuntimeAdapter/PromptBuilder at all, since
    a generative call anywhere in this path would make "same evidence,
    same config, same result" unprovable."""
    for module_path in ("app.services.personal_os.pattern_detectors", "app.services.personal_os.pattern_evidence"):
        imported = _imported_modules(module_path)
        assert not any("runtime_adapter" in name or "prompt_builder" in name for name in imported), (
            f"{module_path} imports a Runtime/PromptBuilder seam - detection must remain deterministic"
        )


def test_experiment_flow_only_reaches_the_runtime_through_runtime_adapter():
    """P4 §12's own narration step (explaining an already-decided
    comparison result) must follow the same seam every other Personal OS
    flow already uses - no second, ad hoc Runtime invocation path."""
    imported = _imported_modules("app.services.personal_os.experiment_flow")
    assert any(name == "app.services.ai.agents.specialists.runtime_adapter" for name in imported)
    assert not any(name == "app.services.ai.runtime.runtime" for name in imported)


def test_experiment_measurement_does_not_touch_the_runtime():
    """P4 §18: metric extraction, baseline/measurement calculation,
    comparison, and outcome classification must all stay deterministic -
    this module may import neither RuntimeAdapter nor PromptBuilder."""
    imported = _imported_modules("app.services.personal_os.experiment_measurement")
    assert not any("runtime_adapter" in name or "prompt_builder" in name for name in imported), (
        "experiment_measurement.py imports a Runtime/PromptBuilder seam - measurement must remain deterministic"
    )


def test_personal_os_package_lives_outside_the_frozen_ai_operating_system():
    """Personal OS is Application layer, not Platform layer - it must
    not live under app/services/ai/, the package
    app/tests/architecture/dependency_rules.py actually scans and
    ARCHITECTURE_FREEZE_v1.md actually freezes."""
    import app.services.personal_os as personal_os_package

    package_path = Path(personal_os_package.__file__).resolve()
    assert "services/ai/" not in str(package_path).replace("\\", "/")
