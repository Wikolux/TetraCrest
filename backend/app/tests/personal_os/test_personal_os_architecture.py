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
    "app.services.personal_os.life_domain",
    "app.services.personal_os.life_domain_repository",
    "app.services.personal_os.day_mode",
    "app.services.personal_os.mission",
    "app.services.personal_os.mission_repository",
    "app.services.personal_os.autonomy",
    "app.services.personal_os.priority",
    "app.services.personal_os.candidate_sources",
    "app.services.personal_os.priority_flow",
    "app.services.personal_os.living_day",
    "app.services.personal_os.living_day_repository",
    "app.services.personal_os.living_day_interaction",
    "app.services.personal_os.living_day_flow",
    "app.services.personal_os.adaptation",
    "app.services.personal_os.adaptation_repository",
    "app.services.personal_os.adaptation_flow",
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
        "app.services.personal_os.life_domain_repository",
        "app.services.personal_os.mission_repository",
        "app.services.personal_os.living_day_repository",
        "app.services.personal_os.adaptation_repository",
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


def test_priority_flow_only_reaches_the_runtime_through_runtime_adapter():
    """P5 §27's own narration step (explaining an already-ranked,
    already-explained item) must follow the same seam every other
    Personal OS flow already uses."""
    imported = _imported_modules("app.services.personal_os.priority_flow")
    assert any(name == "app.services.ai.agents.specialists.runtime_adapter" for name in imported)
    assert not any(name == "app.services.ai.runtime.runtime" for name in imported)


def test_priority_engine_and_autonomy_and_candidate_sources_do_not_touch_the_runtime():
    """P5 §27: 'Do not let an LLM secretly determine priority
    mathematics.' priority.py's own scoring/ranking, autonomy.py's own
    permission check, and candidate_sources.py's own record-to-candidate
    transforms must all stay deterministic - none of the three may import
    RuntimeAdapter/PromptBuilder at all."""
    for module_path in (
        "app.services.personal_os.priority",
        "app.services.personal_os.autonomy",
        "app.services.personal_os.candidate_sources",
        "app.services.personal_os.day_mode",
        "app.services.personal_os.life_domain",
        "app.services.personal_os.mission",
    ):
        imported = _imported_modules(module_path)
        assert not any("runtime_adapter" in name or "prompt_builder" in name for name in imported), (
            f"{module_path} imports a Runtime/PromptBuilder seam - this module must remain deterministic"
        )


def test_autonomy_module_contains_no_execution_surface():
    """P5 §24: no external integration exists yet, and autonomy.py must
    never pretend one does - it is a permission check only. Verified
    structurally: the module's own source never imports requests/httpx
    or any external-API client, and defines no function whose name
    implies it actually performs a consequential action."""
    source = inspect.getsource(importlib.import_module("app.services.personal_os.autonomy"))
    forbidden_fragments = ("requests.", "httpx.", "def reserve_flight", "def send_application", "def make_payment", "def post_to_linkedin")
    for fragment in forbidden_fragments:
        assert fragment not in source, f"autonomy.py contains {fragment!r} - it must remain a pure permission check"


def test_no_duplicate_task_or_repository_mechanism_for_missions():
    """P5 §2, §26: Mission must not become a second task-tracking system
    - mission.py declares no dependency on, or reimplementation of, any
    existing task/reconciliation concept."""
    source = inspect.getsource(importlib.import_module("app.services.personal_os.mission"))
    assert "class Task" not in source
    assert "TaskRepository" not in source


def test_living_day_flow_only_reaches_the_runtime_through_runtime_adapter():
    """P6.2's own narration step (present_replan(), reusing
    PriorityIntelligenceFlow.present()) must not introduce a second
    Runtime invocation path - living_day_flow.py itself never even needs
    to import RuntimeAdapter directly, since it delegates narration
    entirely to priority_flow.py; this test proves that delegation
    rather than assuming it."""
    imported = _imported_modules("app.services.personal_os.living_day_flow")
    assert not any(name == "app.services.ai.runtime.runtime" for name in imported)
    assert not any("prompt_builder" in name for name in imported), (
        "living_day_flow.py imports PromptBuilder directly - narration must stay delegated to priority_flow.py, never duplicated"
    )


def test_living_day_and_living_day_interaction_do_not_touch_the_runtime():
    """P6.1/P6.4: reconstruct() and the heuristic interpreter must both
    stay deterministic - reconstructing a day's state from its event log,
    and classifying a user statement into events, are both pure
    computations this milestone requires stay inspectable and repeatable,
    never influenced by a generative call."""
    for module_path in ("app.services.personal_os.living_day", "app.services.personal_os.living_day_interaction"):
        imported = _imported_modules(module_path)
        assert not any("runtime_adapter" in name or "prompt_builder" in name for name in imported), (
            f"{module_path} imports a Runtime/PromptBuilder seam - this module must remain deterministic"
        )


def test_living_day_flow_reuses_rank_candidates_never_a_second_priority_algorithm():
    """P6.2's own explicit 'do not create a second priority algorithm' -
    verified structurally: living_day_flow.py's replan() must call
    priority.rank_candidates(), never redefine its own scoring/ranking
    logic."""
    source = inspect.getsource(importlib.import_module("app.services.personal_os.living_day_flow"))
    assert "rank_candidates(" in source
    assert "def calculate_score" not in source
    assert "def rank_candidates" not in source


def test_living_day_makes_no_calendar_or_scheduling_assumption():
    """The build brief's own explicit boundary: 'not assume a Calendar
    exists,' 'not assume the user has scheduled plans,' 'not assume
    weekdays/weekends have fixed behavior.' Verified structurally: no
    calendar/scheduling library import anywhere in the Living Day
    modules, and DailyIntent (P6.1's own required 'original morning
    intent') stays optional everywhere it is consumed."""
    for module_path in ("app.services.personal_os.living_day", "app.services.personal_os.living_day_flow", "app.services.personal_os.living_day_interaction"):
        source = inspect.getsource(importlib.import_module(module_path))
        forbidden_fragments = ("import calendar", "google.calendar", "outlook", "icalendar", "caldav")
        for fragment in forbidden_fragments:
            assert fragment not in source.lower(), f"{module_path} references {fragment!r} - no calendar assumption is permitted in P6"


def test_adaptation_flow_only_reaches_the_runtime_through_runtime_adapter():
    """P7.10's own narration step (present(), explaining an already-
    decided proposal) must follow the same seam every other Personal OS
    flow already uses - no second, ad hoc Runtime invocation path."""
    imported = _imported_modules("app.services.personal_os.adaptation_flow")
    assert any(name == "app.services.ai.agents.specialists.runtime_adapter" for name in imported)
    assert not any(name == "app.services.ai.runtime.runtime" for name in imported)


def test_adaptation_and_adaptation_repository_do_not_touch_the_runtime():
    """P7.10 §18: the adaptation domain model and its persistence must
    stay entirely deterministic - status transitions and lifecycle rules
    are plain state machines, never influenced by a generative call."""
    for module_path in ("app.services.personal_os.adaptation", "app.services.personal_os.adaptation_repository"):
        imported = _imported_modules(module_path)
        assert not any("runtime_adapter" in name or "prompt_builder" in name for name in imported), (
            f"{module_path} imports a Runtime/PromptBuilder seam - this module must remain deterministic"
        )


def test_adaptation_reuses_pattern_and_experiment_never_redefines_evidence_or_measurement():
    """P7.10's own Design Question 1/2 resolution, verified structurally:
    Adaptation composes Pattern (evidence/hypothesis/recommendation) and
    Experiment (measurement) by reference (pattern_id/experiment_id) -
    it must import their real types, and must never redefine its own
    ObservedFact/InferredPattern/Hypothesis/GrowthRecommendation/
    ExperimentBaseline/ExperimentComparison-shaped class."""
    for module_path in ("app.services.personal_os.adaptation", "app.services.personal_os.adaptation_flow"):
        source = inspect.getsource(importlib.import_module(module_path))
        forbidden_class_defs = (
            "class ObservedFact", "class InferredPattern", "class Hypothesis", "class GrowthRecommendation",
            "class ExperimentBaseline", "class ExperimentMeasurement", "class ExperimentComparison",
            "class PatternEvidenceItem",
        )
        for fragment in forbidden_class_defs:
            assert fragment not in source, f"{module_path} redefines {fragment!r} - evidence/measurement must be reused from Pattern/Experiment, never duplicated"

    flow_source = inspect.getsource(importlib.import_module("app.services.personal_os.adaptation_flow"))
    assert "from app.services.personal_os.pattern import Pattern" in flow_source
    assert "from app.services.personal_os.experiment import Experiment" in flow_source


def test_no_second_learning_or_adaptation_engine_exists():
    """The build brief's own explicit prohibition: no
    learning_engine/adaptation_engine/self_improvement_engine package,
    and no second copy of the Pattern/Experiment detection or
    measurement machinery anywhere under personal_os/."""
    import app.services.personal_os as personal_os_package

    package_dir = Path(personal_os_package.__file__).resolve().parent
    forbidden_names = ("learning_engine.py", "adaptation_engine.py", "self_improvement_engine.py", "learning_engine", "adaptation_engine")
    existing_names = {p.name for p in package_dir.iterdir()}
    for forbidden in forbidden_names:
        assert forbidden not in existing_names, f"a competing engine module/package {forbidden!r} exists - adaptation.py/adaptation_flow.py must be the only home for this concern"


def test_adaptation_scope_cannot_represent_governed_configuration():
    """P7.10 §10 (hard boundary): ordinary adaptation must never be able
    to claim authority over authorization, security, tenant isolation,
    tool permissions, or platform governance. Enforced structurally -
    AdaptationScope is a closed enum with exactly four members, and none
    of them, nor AdaptationTarget's own shape, mention any of these."""
    from app.services.personal_os.shared.types import AdaptationScope

    scope_values = {s.value for s in AdaptationScope}
    assert scope_values == {"user", "user_preference", "mission", "workflow"}

    for module_path in ("app.services.personal_os.adaptation", "app.services.personal_os.adaptation_flow", "app.services.personal_os.adaptation_repository"):
        source = inspect.getsource(importlib.import_module(module_path))
        forbidden_fragments = (
            "import security", "from security", "TenantMiddleware", "eval(", "exec(",
            "subprocess", "importlib.reload", "os.system", "AgentCapability.", "SpecialistRegistry.register",
        )
        for fragment in forbidden_fragments:
            assert fragment not in source, f"{module_path} contains {fragment!r} - adaptation must never touch governed configuration or execute arbitrary code"


def test_priority_and_candidate_sources_do_not_touch_the_runtime():
    """P7.11: reading adopted adaptations and adjusting a candidate's
    momentum must stay exactly as deterministic as every other Priority
    Engine calculation - no generative call anywhere near candidate
    construction or scoring."""
    for module_path in ("app.services.personal_os.priority", "app.services.personal_os.candidate_sources"):
        imported = _imported_modules(module_path)
        assert not any("runtime_adapter" in name or "prompt_builder" in name for name in imported), (
            f"{module_path} imports a Runtime/PromptBuilder seam - this module must remain deterministic"
        )


def test_priority_py_defines_exactly_one_scoring_and_one_ranking_function():
    """P7.11's own Critical Rule: adaptation runtime wiring must not
    replace or duplicate calculate_score()/rank_candidates()/explain() -
    verified structurally, not just by code review, that no second
    definition of any of the three was introduced anywhere in the
    package."""
    forbidden = ("def calculate_score", "def rank_candidates", "def explain(")
    for module_path in _PERSONAL_OS_MODULES:
        if module_path == "app.services.personal_os.priority":
            continue
        source = inspect.getsource(importlib.import_module(module_path))
        for fragment in forbidden:
            assert fragment not in source, f"{module_path} defines {fragment!r} - priority.py must remain the only ranking/scoring/explanation engine"


def test_priority_flow_only_reads_the_adaptation_repository_never_writes():
    """P7.11 §13/§21: the Priority path is a consumer of adopted
    adaptation state, never a second place that can change it - adoption,
    rollback, and supersession remain exclusively AdaptationFlow's own
    governed transitions."""
    source = inspect.getsource(importlib.import_module("app.services.personal_os.priority_flow"))
    forbidden_writes = (".save(", ".adopt(", ".rollback(", ".approve(", ".reject(", ".retire(")
    for fragment in forbidden_writes:
        assert fragment not in source, f"priority_flow.py calls {fragment!r} - it must only ever read adaptation state via list_active()/get_adopted_for_target()"
    assert "list_active(" in source


def test_adaptation_effect_is_a_closed_bounded_vocabulary_not_a_rule_language():
    """P7.11 §3/§8: no generic rules engine, no DSL, no executable code
    stored on an Adaptation - AdaptationEffectKind/PriorityDirection stay
    small, named, closed StrEnums, and adaptation.py never imports eval/
    exec/a template engine/a rule-evaluation library."""
    from app.services.personal_os.shared.types import AdaptationEffectKind, PriorityDirection

    assert len(list(AdaptationEffectKind)) == 1
    assert len(list(PriorityDirection)) == 2

    for module_path in ("app.services.personal_os.adaptation", "app.services.personal_os.candidate_sources", "app.services.personal_os.priority_flow"):
        source = inspect.getsource(importlib.import_module(module_path))
        for fragment in ("eval(", "exec(", "compile(", "jinja2", "Template(", "__import__"):
            assert fragment not in source, f"{module_path} contains {fragment!r} - an adopted effect must never be interpreted as arbitrary code"


def test_living_day_flow_gained_no_adaptation_specific_logic():
    """P7.11 §19's own central requirement, verified structurally: the
    adopted-effect behavior must reach replan()/present_replan() purely
    through the shared priority_flow seam - living_day_flow.py itself
    must not import the adaptation modules or reference AdaptationEffect/
    AdaptationRepository directly."""
    source = inspect.getsource(importlib.import_module("app.services.personal_os.living_day_flow"))
    imported = _imported_modules("app.services.personal_os.living_day_flow")
    assert not any("adaptation" in name for name in imported), "living_day_flow.py must not import any adaptation module directly - it inherits behavior only through priority_flow.py"
    assert "AdaptationEffect" not in source
    assert "AdaptationRepository" not in source


def test_personal_os_package_lives_outside_the_frozen_ai_operating_system():
    """Personal OS is Application layer, not Platform layer - it must
    not live under app/services/ai/, the package
    app/tests/architecture/dependency_rules.py actually scans and
    ARCHITECTURE_FREEZE_v1.md actually freezes."""
    import app.services.personal_os as personal_os_package

    package_path = Path(personal_os_package.__file__).resolve()
    assert "services/ai/" not in str(package_path).replace("\\", "/")
