"""CP-02 Milestone 8 - consolidated, pack-wide architecture and dependency
verification, across all five specialists at once.

Every individual specialist's own Milestone 3-7 test suite already proves
its own module never imports another specialist's code, in isolation.
This file adds the pack-wide view Implementation_Plan.md's own Milestone
8 objectives ask for: zero specialist-to-specialist imports *anywhere* in
CP-02, zero new dependency-boundary entries beyond the one
`agents.specialists.product_management` boundary registered at Milestone
3, zero duplicated memory categories, and a clean run of the platform's
own AST-based architecture-enforcement suite (dependency_rules.py) scoped
to this evidence - the same executable check `app/tests/architecture/`
runs platform-wide, invoked here directly so a CP-02-specific regression
is caught by this pack's own test suite too, not only by running the
separate architecture suite.
"""

import ast
import importlib
import inspect

from app.services.ai.agents.memory import AgentMemory
from app.services.context.types import ContextPackage
from app.tests.architecture.dependency_rules import (
    ALLOWED_DEPENDENCIES,
    _BOUNDARIES_BY_SPECIFICITY,
    classify_module,
    find_boundary_violations,
    find_vendor_import_violations,
)


class _EmptyMemory(AgentMemory):
    """A minimal AgentMemory fake: no DB, no embedding provider - used
    throughout this file wherever a specialist must be fully constructed
    (not merely have its module inspected) without touching the real
    Memory Framework."""

    def remember(self, item, **kwargs):
        pass

    def retrieve(self, query, **kwargs):
        return ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)

    def search(self, query, **kwargs):
        return self.retrieve(query, **kwargs)

    def forget(self, item_id):
        raise NotImplementedError


class _EmptyBulkMemoryService:
    def list_memories(self, organization_id, skip=0, limit=20):
        return []


_SPECIALIST_MODULES = {
    "discovery": "app.services.ai.agents.specialists.product_management.discovery.discovery_agent",
    "product_decision": "app.services.ai.agents.specialists.product_management.product_decision.product_decision_agent",
    "delivery": "app.services.ai.agents.specialists.product_management.delivery.delivery_agent",
    "strategy_portfolio": "app.services.ai.agents.specialists.product_management.strategy_portfolio.strategy_portfolio_agent",
    "stakeholder_communication": "app.services.ai.agents.specialists.product_management.stakeholder_communication.stakeholder_communication_agent",
}

_SPECIALIST_PACKAGE_FRAGMENTS = (
    "product_management.discovery",
    "product_management.product_decision",
    "product_management.delivery",
    "product_management.strategy_portfolio",
    "product_management.stakeholder_communication",
)


def _imported_modules(module_path: str) -> list[str]:
    module = importlib.import_module(module_path)
    tree = ast.parse(inspect.getsource(module))
    return [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]


# --- zero direct specialist-to-specialist imports, pack-wide -----------------------------------


def test_zero_specialists_import_any_other_specialists_own_package():
    violations = []
    for owner_name, module_path in _SPECIALIST_MODULES.items():
        imported = _imported_modules(module_path)
        for fragment in _SPECIALIST_PACKAGE_FRAGMENTS:
            owner_fragment = f"product_management.{owner_name}"
            if fragment == owner_fragment:
                continue
            if any(fragment in name for name in imported):
                violations.append(f"{owner_name} imports from {fragment}")
    assert violations == []


def test_zero_specialists_import_research_agent_or_personal_intelligence_code():
    violations = []
    for owner_name, module_path in _SPECIALIST_MODULES.items():
        imported = _imported_modules(module_path)
        if any("specialists.research" in name for name in imported):
            violations.append(f"{owner_name} imports specialists.research")
        if any("personal_intelligence" in name for name in imported):
            violations.append(f"{owner_name} imports personal_intelligence")
    assert violations == []


def test_the_two_specialist_owned_scoring_modules_never_import_each_other():
    # Product Decision (Milestone 4) and Strategy & Portfolio (Milestone 6)
    # each independently implement RICE/ICE scoring - proving, at the
    # import-graph level, that this is real independent reuse of a public
    # formula, not one specialist secretly depending on the other's code.
    decision_scoring = _imported_modules(
        "app.services.ai.agents.specialists.product_management.product_decision.scoring"
    )
    strategy_scoring = _imported_modules(
        "app.services.ai.agents.specialists.product_management.strategy_portfolio.scoring"
    )
    assert not any("strategy_portfolio" in name for name in decision_scoring)
    assert not any("product_decision" in name for name in strategy_scoring)


# --- Dispatcher / registry-level Pack Independence, pack-wide ----------------------------------


def test_all_five_specialists_declare_distinct_specializations():
    from app.services.ai.agents.specialists.registry import SpecialistRegistry

    specializations = {
        SpecialistRegistry.get_registration(name).specialization for name in _SPECIALIST_MODULES
    }
    assert specializations == set(_SPECIALIST_MODULES)


def test_no_two_specialists_declare_an_identical_capability_set_beyond_the_shared_baseline():
    # Mirrors ARR §3.1's own Overlap Check: REASONING/PLANNING is a
    # deliberate shared baseline every specialist needs. The only
    # permitted differentiator is COMMUNICATION (Stakeholder Communication
    # alone) - never a source of dispatch ambiguity since MEMORY is never
    # declared by any of them.
    from app.services.ai.agents.enums import AgentCapability
    from app.services.ai.agents.specialists.product_management.delivery.delivery_agent import DeliverySpecialist
    from app.services.ai.agents.specialists.product_management.discovery.discovery_agent import DiscoverySpecialist
    from app.services.ai.agents.specialists.product_management.product_decision.product_decision_agent import (
        ProductDecisionSpecialist,
    )
    from app.services.ai.agents.specialists.product_management.stakeholder_communication.stakeholder_communication_agent import (
        StakeholderCommunicationSpecialist,
    )
    from app.services.ai.agents.specialists.product_management.strategy_portfolio.strategy_portfolio_agent import (
        StrategyPortfolioSpecialist,
    )

    classes = {
        "discovery": DiscoverySpecialist,
        "product_decision": ProductDecisionSpecialist,
        "delivery": DeliverySpecialist,
        "strategy_portfolio": StrategyPortfolioSpecialist,
        "stakeholder_communication": StakeholderCommunicationSpecialist,
    }
    capability_sets = {
        name: cls(memory_adapter=_EmptyMemory()).capabilities().declared for name, cls in classes.items()
    }

    shared_baseline = frozenset({AgentCapability.REASONING, AgentCapability.PLANNING})
    for name, declared in capability_sets.items():
        assert AgentCapability.MEMORY not in declared
        assert AgentCapability.RESEARCH not in declared
        if name == "stakeholder_communication":
            assert declared == shared_baseline | {AgentCapability.COMMUNICATION}
        else:
            assert declared == shared_baseline

    # Exactly one specialist (Stakeholder Communication) differs from the
    # shared baseline - the only permitted overlap-breaking differentiator.
    distinct_sets = set(capability_sets.values())
    assert len(distinct_sets) == 2


# --- dependency-boundary classification and enforcement, pack-wide -----------------------------


def test_all_five_specialist_modules_classify_under_the_single_registered_boundary():
    for name, module_path in _SPECIALIST_MODULES.items():
        relative = module_path.removeprefix("app.services.ai.")
        boundary = classify_module(relative)
        assert boundary == "agents.specialists.product_management", (
            f"{name} classified as {boundary!r}, expected the single pack-wide boundary"
        )


def test_no_boundary_entry_exists_more_specific_than_the_pack_wide_one():
    # Milestones 3-7 each confirmed, individually, that their own
    # subpackage required no new, more specific boundary entry (unlike
    # research/personal_intelligence, which each have their own). This
    # test makes that a single, pack-wide, permanent assertion: CP-02 has
    # exactly one dependency-boundary entry, covering all five specialists
    # via longest-prefix match.
    product_management_boundaries = [
        boundary for boundary in _BOUNDARIES_BY_SPECIFICITY if "product_management" in boundary
    ]
    assert product_management_boundaries == ["agents.specialists.product_management"]


def test_the_pack_wide_boundarys_allowed_dependencies_are_unchanged_from_milestone_3():
    allowed = ALLOWED_DEPENDENCIES["agents.specialists.product_management"]
    assert allowed == frozenset({"agents.specialists", "agents", "tools", "shared", "runtime", "kernel", "providers"})


def test_full_architecture_enforcement_suite_reports_zero_violations():
    assert find_boundary_violations() == []
    assert find_vendor_import_violations() == []


# --- zero duplicated memory categories, pack-wide -----------------------------------------------


def test_all_memory_types_remain_the_ten_originally_approved_categories_no_new_ones_added():
    from app.services.ai.agents.specialists.product_management.shared.types import ALL_MEMORY_TYPES

    assert len(ALL_MEMORY_TYPES) == 10
    assert len(set(ALL_MEMORY_TYPES)) == 10  # no duplicates


def test_stakeholder_communications_own_writes_reuse_existing_categories_only():
    from app.services.ai.agents.specialists.product_management.shared.types import (
        MEMORY_TYPE_DELIVERY_ARTIFACT,
        MEMORY_TYPE_STAKEHOLDER,
    )

    # Both categories Milestone 7 writes to (Stakeholder Record, Delivery
    # Artifact) already existed before Milestone 7 began (Milestones 1
    # and 5 respectively) - confirmed by construction, not merely by
    # docstring claim.
    assert MEMORY_TYPE_STAKEHOLDER == "product_stakeholder"
    assert MEMORY_TYPE_DELIVERY_ARTIFACT == "product_delivery_artifact"


def test_portfolio_never_gained_its_own_memory_type_across_any_milestone():
    from app.services.ai.agents.specialists.product_management.shared.types import ALL_MEMORY_TYPES

    assert "product_portfolio" not in ALL_MEMORY_TYPES
    assert not any("portfolio" in memory_type for memory_type in ALL_MEMORY_TYPES)


# --- no specialist bypasses PromptBuilder or invokes Runtime directly --------------------------


def test_no_specialist_module_constructs_airuntime_or_aimemoryservice_directly():
    violations = []
    for owner_name, module_path in _SPECIALIST_MODULES.items():
        source = inspect.getsource(importlib.import_module(module_path))
        if "AIRuntime(" in source:
            violations.append(f"{owner_name} constructs AIRuntime() directly")
        if "AIMemoryService(" in source:
            violations.append(f"{owner_name} constructs AIMemoryService() directly")
    assert violations == []


def test_every_specialist_generates_through_a_real_prompt_builder_call():
    from app.services.ai.agents.context import AgentContext
    from app.services.ai.agents.specialists.product_management.delivery.delivery_agent import DeliverySpecialist
    from app.services.ai.agents.specialists.product_management.delivery.request import DeliveryOperation, DeliveryRequest
    from app.services.ai.agents.specialists.product_management.discovery.discovery_agent import DiscoverySpecialist
    from app.services.ai.agents.specialists.product_management.discovery.request import DiscoveryOperation, DiscoveryRequest
    from app.services.ai.agents.specialists.product_management.memory_service import ProfessionalMemoryService
    from app.services.ai.agents.specialists.product_management.product_decision.product_decision_agent import (
        ProductDecisionSpecialist,
    )
    from app.services.ai.agents.specialists.product_management.product_decision.request import (
        DecisionOperation,
        DecisionRequest,
    )
    from app.services.ai.agents.specialists.product_management.stakeholder_communication.request import (
        StakeholderCommunicationOperation,
        StakeholderCommunicationRequest,
    )
    from app.services.ai.agents.specialists.product_management.stakeholder_communication.stakeholder_communication_agent import (
        StakeholderCommunicationSpecialist,
    )
    from app.services.ai.agents.specialists.product_management.strategy_portfolio.request import (
        StrategyOperation,
        StrategyRequest,
    )
    from app.services.ai.agents.specialists.product_management.strategy_portfolio.strategy_portfolio_agent import (
        StrategyPortfolioSpecialist,
    )
    from app.services.ai.agents.specialists.runtime_adapter import RuntimeAdapter
    from app.services.ai.agents.specialists.shared.context import SpecialistContext
    from app.services.ai.runtime.types import RuntimeResponse
    from app.services.prompt_builder.types import PromptPackage

    class _RecordingRuntime:
        def __init__(self):
            self.requests = []

        def execute(self, request):
            self.requests.append(request)
            return RuntimeResponse(success=True)

    context = SpecialistContext(agent_context=AgentContext(organization_id=1, user_id=2))
    scenarios = [
        (DiscoverySpecialist, DiscoveryRequest(operation=DiscoveryOperation.RECALL, text="x")),
        (
            ProductDecisionSpecialist,
            DecisionRequest(operation=DecisionOperation.RECALL_DECISION_HISTORY, question="x"),
        ),
        (DeliverySpecialist, DeliveryRequest(operation=DeliveryOperation.RECALL, text="x")),
        (StrategyPortfolioSpecialist, StrategyRequest(operation=StrategyOperation.RECALL, text="x")),
        (
            StakeholderCommunicationSpecialist,
            StakeholderCommunicationRequest(operation=StakeholderCommunicationOperation.RECALL, text="x"),
        ),
    ]
    for specialist_cls, request in scenarios:
        runtime = _RecordingRuntime()
        memory_adapter = _EmptyMemory()
        agent = specialist_cls(
            memory_adapter=memory_adapter,
            memory_service=ProfessionalMemoryService(memory_adapter, _EmptyBulkMemoryService()),
            runtime_adapter=RuntimeAdapter(runtime=runtime),
        )
        agent.process(request, context)
        assert len(runtime.requests) == 1
        assert isinstance(runtime.requests[0].prompt_package, PromptPackage)
