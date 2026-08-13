"""ProfessionalMemoryService - CP-02's single memory gateway (Milestone 2).

No fake here ever touches AIMemoryService/MemoryRetrievalPipeline/a real
DB - a hand-rolled _FakeMemory (implementing AgentMemory) and
_FakeMemoryService (AIMemoryService-shaped) record every call so tests
assert on exactly what was delegated, without depending on MemoryAdapter's
own wiring (already covered by test_memory_adapter.py) or on
MemoryRetrievalPipeline's own internals (already covered by
test_memory_retrieval_pipeline.py). This mirrors
test_memory_service.py's (CP-01) and test_insight_memory_service.py's
(CP-01.3) own conventions exactly.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.specialists.product_management.memory_service import ProfessionalMemoryService
from app.services.ai.agents.specialists.product_management.shared.decision_record import (
    DecisionFramework,
    DecisionRecord,
)
from app.services.ai.agents.specialists.product_management.shared.discovery_finding import (
    DiscoveryFinding,
    HypothesisStatus,
)
from app.services.ai.agents.specialists.product_management.shared.feature import FeatureInitiative
from app.services.ai.agents.specialists.product_management.shared.metric import Metric
from app.services.ai.agents.specialists.product_management.shared.portfolio import Portfolio
from app.services.ai.agents.specialists.product_management.shared.product import Product
from app.services.ai.agents.specialists.product_management.shared.research_finding import ResearchFinding
from app.services.ai.agents.specialists.product_management.shared.roadmap import RoadmapItem
from app.services.ai.agents.specialists.product_management.shared.stakeholder import Stakeholder
from app.services.ai.agents.specialists.product_management.shared.types import (
    MEMORY_TYPE_DECISION,
    MEMORY_TYPE_DISCOVERY_FINDING,
    MEMORY_TYPE_FEATURE,
    MEMORY_TYPE_METRIC,
    MEMORY_TYPE_PRODUCT,
    MEMORY_TYPE_RESEARCH_FINDING,
    MEMORY_TYPE_ROADMAP,
    MEMORY_TYPE_STAKEHOLDER,
)
from app.services.context.types import ContextPackage


class _FakeMemory(AgentMemory):
    """Implements the AgentMemory ABC directly - proves the contract is
    enforceable, not just documented, per Philosophy.md #8."""

    def __init__(self):
        self.remembered = []
        self.retrieve_calls = []
        self.search_calls = []

    def remember(self, item, **kwargs):
        self.remembered.append((item, kwargs))

    def retrieve(self, query, **kwargs):
        self.retrieve_calls.append((query, kwargs))
        return ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)

    def search(self, query, **kwargs):
        self.search_calls.append((query, kwargs))
        return ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)

    def forget(self, item_id):
        raise NotImplementedError


class _Row:
    def __init__(self, id, organization_id, content, memory_type, title, created_at=None):
        self.id = id
        self.organization_id = organization_id
        self.content = content
        self.memory_type = memory_type
        self.title = title
        self.created_at = created_at or datetime.now(UTC)


class _FakeMemoryService:
    """AIMemoryService-shaped: only list_memories() is exercised, the
    same unmodified method InsightMemoryService already depends on."""

    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []

    def list_memories(self, organization_id, skip=0, limit=20):
        self.calls.append((organization_id, skip, limit))
        matching = [row for row in self.rows if row.organization_id == organization_id]
        return matching[skip : skip + limit]


def _service(**overrides):
    memory = overrides.pop("memory", None) or _FakeMemory()
    memory_service = overrides.pop("memory_service", None) or _FakeMemoryService()
    return ProfessionalMemoryService(memory, memory_service)


# --- construction / defaults ------------------------------------------------------------------


def test_defaults_to_memory_adapter_and_ai_memory_service_when_none_given():
    # Both defaults eagerly construct real, DB/embedding-backed
    # collaborators - not something a unit test should trigger. This only
    # asserts the constructor's default *types*, via the signature,
    # without instantiating them - mirroring
    # test_memory_service.py::test_defaults_to_a_memory_adapter_when_none_given
    # and test_insight_memory_service.py's identical precedent.
    import inspect

    params = inspect.signature(ProfessionalMemoryService.__init__).parameters
    assert params["memory"].default is None
    assert params["memory_service"].default is None
    source = inspect.getsource(ProfessionalMemoryService.__init__)
    assert "MemoryAdapter()" in source
    assert "AIMemoryService()" in source


def test_uses_the_injected_memory_and_memory_service_instances():
    memory = _FakeMemory()
    memory_service = _FakeMemoryService()
    service = ProfessionalMemoryService(memory, memory_service)
    assert service.memory is memory
    assert service.memory_service is memory_service


# --- remember_product ---------------------------------------------------------------------


def test_remember_product_uses_the_product_name_and_product_memory_type():
    memory = _FakeMemory()
    service = _service(memory=memory)
    product = Product(name="AI Operating System", owning_pm="Vic")

    service.remember_product(product, organization_id=1, user_id=7)

    content, kwargs = memory.remembered[0]
    assert content == product.to_memory_content()
    assert kwargs == {
        "organization_id": 1,
        "user_id": 7,
        "memory_type": MEMORY_TYPE_PRODUCT,
        "title": "AI Operating System",
    }


def test_remember_product_defaults_user_id_to_none():
    memory = _FakeMemory()
    service = _service(memory=memory)
    service.remember_product(Product(name="x"), organization_id=1)
    assert memory.remembered[0][1]["user_id"] is None


# --- remember_feature ----------------------------------------------------------------------


def test_remember_feature_uses_the_feature_title_and_feature_memory_type():
    memory = _FakeMemory()
    service = _service(memory=memory)
    feature = FeatureInitiative(title="Async status updates")

    service.remember_feature(feature, organization_id=1)

    content, kwargs = memory.remembered[0]
    assert content == feature.to_memory_content()
    assert kwargs["memory_type"] == MEMORY_TYPE_FEATURE
    assert kwargs["title"] == "Async status updates"


# --- remember_roadmap -----------------------------------------------------------------------


def test_remember_roadmap_uses_the_item_title_and_roadmap_memory_type():
    memory = _FakeMemory()
    service = _service(memory=memory)
    item = RoadmapItem(title="Ship CP-02 v1")

    service.remember_roadmap(item, organization_id=1)

    content, kwargs = memory.remembered[0]
    assert content == item.to_memory_content()
    assert kwargs["memory_type"] == MEMORY_TYPE_ROADMAP
    assert kwargs["title"] == "Ship CP-02 v1"


# --- remember_metric ------------------------------------------------------------------------


def test_remember_metric_uses_the_metric_name_and_metric_memory_type():
    memory = _FakeMemory()
    service = _service(memory=memory)
    metric = Metric(name="Weekly active PMs", is_north_star=True)

    service.remember_metric(metric, organization_id=1)

    content, kwargs = memory.remembered[0]
    assert content == metric.to_memory_content()
    assert kwargs["memory_type"] == MEMORY_TYPE_METRIC
    assert kwargs["title"] == "Weekly active PMs"


# --- remember_discovery ----------------------------------------------------------------------


def test_remember_discovery_titles_the_memory_with_the_hypothesis_status():
    memory = _FakeMemory()
    service = _service(memory=memory)
    finding = DiscoveryFinding(summary="s", source="5 interviews", status=HypothesisStatus.VALIDATED)

    service.remember_discovery(finding, organization_id=1)

    content, kwargs = memory.remembered[0]
    assert content == finding.to_memory_content()
    assert kwargs["memory_type"] == MEMORY_TYPE_DISCOVERY_FINDING
    assert kwargs["title"] == "Discovery finding (validated)"


# --- remember_research -----------------------------------------------------------------------


def test_remember_research_titles_the_memory_with_the_source_question():
    memory = _FakeMemory()
    service = _service(memory=memory)
    finding = ResearchFinding(summary="s", source_question="What do competitors offer?")

    service.remember_research(finding, organization_id=1)

    content, kwargs = memory.remembered[0]
    assert content == finding.to_memory_content()
    assert kwargs["memory_type"] == MEMORY_TYPE_RESEARCH_FINDING
    assert kwargs["title"] == "Research finding: What do competitors offer?"


# --- remember_stakeholder --------------------------------------------------------------------


def test_remember_stakeholder_uses_the_stakeholder_name_and_stakeholder_memory_type():
    memory = _FakeMemory()
    service = _service(memory=memory)
    stakeholder = Stakeholder(name="Jane")

    service.remember_stakeholder(stakeholder, organization_id=1)

    content, kwargs = memory.remembered[0]
    assert content == stakeholder.to_memory_content()
    assert kwargs["memory_type"] == MEMORY_TYPE_STAKEHOLDER
    assert kwargs["title"] == "Jane"


# --- remember_decision ----------------------------------------------------------------------


def _decision_record(**overrides):
    defaults = dict(
        title="Build vs. buy: research delegation",
        framework=DecisionFramework.BUILD_VS_BUY,
        rationale="ResearchAgent already exists and is proven",
        counterpoint="A dedicated pipeline could be more product-specific",
        supporting_memory_ids=(10, 11),
    )
    defaults.update(overrides)
    return DecisionRecord(**defaults)


def test_remember_decision_uses_the_decision_title_and_decision_memory_type():
    memory = _FakeMemory()
    service = _service(memory=memory)
    decision = _decision_record()

    service.remember_decision(decision, organization_id=1)

    content, kwargs = memory.remembered[0]
    assert content == decision.to_memory_content()
    assert kwargs["memory_type"] == MEMORY_TYPE_DECISION
    assert kwargs["title"] == "Build vs. buy: research delegation"


def test_remember_decision_content_carries_the_full_evidence_and_counterpoint_trail():
    memory = _FakeMemory()
    service = _service(memory=memory)
    service.remember_decision(_decision_record(), organization_id=1)

    content, _ = memory.remembered[0]
    assert "build_vs_buy" in content
    assert "10, 11" in content
    assert "A dedicated pipeline could be more product-specific" in content


def test_remember_craft_record_uses_pm_craft_record_memory_type():
    from app.services.ai.agents.specialists.product_management.shared.pm_craft_record import PMCraftRecord
    from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_PM_CRAFT_RECORD

    memory = _FakeMemory()
    service = _service(memory=memory)
    record = PMCraftRecord(framework=DecisionFramework.RICE, decision_title="Onboarding revamp", evidence_count=2)

    service.remember_craft_record(record, organization_id=1)

    content, kwargs = memory.remembered[0]
    assert content == record.to_memory_content()
    assert kwargs["memory_type"] == MEMORY_TYPE_PM_CRAFT_RECORD
    assert "Onboarding revamp" in kwargs["title"]


def test_remember_delivery_artifact_uses_delivery_artifact_memory_type():
    from app.services.ai.agents.specialists.product_management.shared.delivery_artifact import (
        DeliveryArtifact,
        DeliveryArtifactType,
    )
    from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_DELIVERY_ARTIFACT

    memory = _FakeMemory()
    service = _service(memory=memory)
    artifact = DeliveryArtifact(
        title="Onboarding revamp spec",
        artifact_type=DeliveryArtifactType.SPEC,
        content="Structured spec grounded in discovery evidence.",
        feature_title="Onboarding revamp",
        linked_evidence_ids=(1, 2),
    )

    service.remember_delivery_artifact(artifact, organization_id=1)

    content, kwargs = memory.remembered[0]
    assert content == artifact.to_memory_content()
    assert kwargs["memory_type"] == MEMORY_TYPE_DELIVERY_ARTIFACT
    assert kwargs["title"] == "Onboarding revamp spec"


# --- remember_portfolio (the entity with no memory_type/to_memory_content of its own) --------


def test_remember_portfolio_writes_under_the_roadmap_memory_type():
    # Portfolio deliberately has no memory_type of its own (Milestone 1);
    # Architecture §12 / ARR §4 assign it the same owner as Roadmap State.
    memory = _FakeMemory()
    service = _service(memory=memory)
    portfolio = Portfolio(product_names=("AI OS", "Website"), priority_notes="AI OS is higher priority")

    service.remember_portfolio(portfolio, organization_id=1)

    content, kwargs = memory.remembered[0]
    assert kwargs["memory_type"] == MEMORY_TYPE_ROADMAP
    assert kwargs["title"] == "Portfolio snapshot"
    assert "AI OS, Website" in content
    assert "AI OS is higher priority" in content


def test_remember_portfolio_does_not_introduce_a_new_memory_type():
    from app.services.ai.agents.specialists.product_management.shared.types import ALL_MEMORY_TYPES

    memory = _FakeMemory()
    service = _service(memory=memory)
    service.remember_portfolio(Portfolio(), organization_id=1)

    _, kwargs = memory.remembered[0]
    assert kwargs["memory_type"] in ALL_MEMORY_TYPES


def test_remember_portfolio_handles_an_empty_portfolio_without_raising():
    memory = _FakeMemory()
    service = _service(memory=memory)
    service.remember_portfolio(Portfolio(), organization_id=1)

    content, _ = memory.remembered[0]
    assert "no products yet" in content


def test_remember_portfolio_omits_priority_notes_clause_when_blank():
    memory = _FakeMemory()
    service = _service(memory=memory)
    service.remember_portfolio(Portfolio(product_names=("A",)), organization_id=1)

    content, _ = memory.remembered[0]
    assert content == "Portfolio: A."


# --- recall (semantic, via AgentMemory.retrieve / MemoryRetrievalPipeline) -------------------


def test_recall_scopes_retrieval_to_memories_only():
    memory = _FakeMemory()
    service = _service(memory=memory)

    service.recall("what products exist", organization_id=1)

    query, kwargs = memory.retrieve_calls[0]
    assert query == "what products exist"
    assert kwargs["organization_id"] == 1
    assert kwargs["scope"] == "memories"


def test_recall_uses_default_limit_and_max_context_tokens():
    memory = _FakeMemory()
    service = _service(memory=memory)
    service.recall("query", organization_id=1)

    _, kwargs = memory.retrieve_calls[0]
    assert kwargs["limit"] == 10
    assert kwargs["max_context_tokens"] == 4000


def test_recall_honors_explicit_limit_and_max_context_tokens():
    memory = _FakeMemory()
    service = _service(memory=memory)
    service.recall("query", organization_id=1, limit=3, max_context_tokens=500)

    _, kwargs = memory.retrieve_calls[0]
    assert kwargs["limit"] == 3
    assert kwargs["max_context_tokens"] == 500


def test_recall_returns_a_context_package():
    memory = _FakeMemory()
    service = _service(memory=memory)
    assert isinstance(service.recall("query", organization_id=1), ContextPackage)


def test_recall_never_calls_search():
    memory = _FakeMemory()
    service = _service(memory=memory)
    service.recall("query", organization_id=1)
    assert memory.search_calls == []


# --- search (via AgentMemory.search) ----------------------------------------------------------


def test_search_scopes_retrieval_to_memories_only():
    memory = _FakeMemory()
    service = _service(memory=memory)

    service.search("what products exist", organization_id=1)

    query, kwargs = memory.search_calls[0]
    assert query == "what products exist"
    assert kwargs["organization_id"] == 1
    assert kwargs["scope"] == "memories"


def test_search_uses_default_limit_and_max_context_tokens():
    memory = _FakeMemory()
    service = _service(memory=memory)
    service.search("query", organization_id=1)

    _, kwargs = memory.search_calls[0]
    assert kwargs["limit"] == 10
    assert kwargs["max_context_tokens"] == 4000


def test_search_returns_a_context_package():
    memory = _FakeMemory()
    service = _service(memory=memory)
    assert isinstance(service.search("query", organization_id=1), ContextPackage)


def test_search_never_calls_retrieve():
    memory = _FakeMemory()
    service = _service(memory=memory)
    service.search("query", organization_id=1)
    assert memory.retrieve_calls == []


def test_search_delegates_through_agent_memorys_own_search_method_not_a_reimplementation():
    # search() must call self.memory.search(), never internally call
    # self.recall()/self.memory.retrieve() - MemoryAdapter's own choice
    # of how search relates to retrieve stays entirely encapsulated
    # there, never duplicated at the service layer.
    import inspect

    source = inspect.getsource(ProfessionalMemoryService.search)
    assert "self.memory.search(" in source
    assert "self.memory.retrieve(" not in source
    assert "self.recall(" not in source


# --- list_by_memory_type (bulk, via AIMemoryService.list_memories, unmodified) ----------------


def _row(id_, organization_id=1, memory_type=MEMORY_TYPE_PRODUCT, content="content", title=None, created_at=None):
    return _Row(id_, organization_id, content, memory_type, title, created_at)


def test_list_by_memory_type_returns_only_matching_rows():
    rows = [
        _row(1, memory_type=MEMORY_TYPE_PRODUCT),
        _row(2, memory_type=MEMORY_TYPE_DECISION),
        _row(3, memory_type=MEMORY_TYPE_PRODUCT),
    ]
    service = _service(memory_service=_FakeMemoryService(rows))

    items = service.list_by_memory_type(MEMORY_TYPE_PRODUCT, organization_id=1)

    assert {item.resource_id for item in items} == {1, 3}
    assert all(item.metadata["memory_type"] == MEMORY_TYPE_PRODUCT for item in items)


def test_list_by_memory_type_converts_rows_to_context_items():
    rows = [_row(1, memory_type=MEMORY_TYPE_STAKEHOLDER, content="Stakeholder: Jane.", title="Jane")]
    service = _service(memory_service=_FakeMemoryService(rows))

    items = service.list_by_memory_type(MEMORY_TYPE_STAKEHOLDER, organization_id=1)

    assert len(items) == 1
    assert items[0].resource_type == "memory"
    assert items[0].resource_id == 1
    assert items[0].content == "Stakeholder: Jane."
    assert items[0].metadata == {"memory_type": MEMORY_TYPE_STAKEHOLDER, "title": "Jane"}


def test_list_by_memory_type_defaults_title_to_empty_string_when_none():
    rows = [_row(1, title=None)]
    service = _service(memory_service=_FakeMemoryService(rows))
    items = service.list_by_memory_type(MEMORY_TYPE_PRODUCT, organization_id=1)
    assert items[0].metadata["title"] == ""


def test_list_by_memory_type_scopes_by_organization_id():
    rows = [_row(1, organization_id=1), _row(2, organization_id=2)]
    service = _service(memory_service=_FakeMemoryService(rows))

    items = service.list_by_memory_type(MEMORY_TYPE_PRODUCT, organization_id=1)

    assert [item.resource_id for item in items] == [1]


def test_list_by_memory_type_on_an_empty_organization_returns_nothing():
    service = _service(memory_service=_FakeMemoryService([]))
    assert service.list_by_memory_type(MEMORY_TYPE_PRODUCT, organization_id=1) == ()


def test_list_by_memory_type_returns_nothing_when_no_row_matches_the_requested_type():
    rows = [_row(1, memory_type=MEMORY_TYPE_DECISION)]
    service = _service(memory_service=_FakeMemoryService(rows))
    assert service.list_by_memory_type(MEMORY_TYPE_PRODUCT, organization_id=1) == ()


def test_list_by_memory_type_paginates_through_list_memories():
    rows = [_row(i, memory_type=MEMORY_TYPE_PRODUCT) for i in range(1, 251)]
    memory_service = _FakeMemoryService(rows)
    service = _service(memory_service=memory_service)

    items = service.list_by_memory_type(MEMORY_TYPE_PRODUCT, organization_id=1, maximum=250)

    assert len(items) == 250
    assert len(memory_service.calls) == 3  # 100 + 100 + 50


def test_list_by_memory_type_respects_the_maximum_cap():
    rows = [_row(i, memory_type=MEMORY_TYPE_PRODUCT) for i in range(1, 500)]
    service = _service(memory_service=_FakeMemoryService(rows))

    items = service.list_by_memory_type(MEMORY_TYPE_PRODUCT, organization_id=1, maximum=30)

    assert len(items) == 30


def test_list_by_memory_type_stops_paginating_once_a_short_page_is_returned():
    rows = [_row(i, memory_type=MEMORY_TYPE_PRODUCT) for i in range(1, 51)]
    memory_service = _FakeMemoryService(rows)
    service = _service(memory_service=memory_service)

    items = service.list_by_memory_type(MEMORY_TYPE_PRODUCT, organization_id=1, maximum=200)

    assert len(items) == 50
    assert len(memory_service.calls) == 1


def test_list_by_memory_type_never_calls_agent_memory_retrieve_or_search():
    # the defining property of this read path: it must not duplicate
    # semantic retrieval - it never touches AgentMemory at all.
    memory = _FakeMemory()
    memory_service = _FakeMemoryService([_row(1)])
    service = ProfessionalMemoryService(memory, memory_service)

    service.list_by_memory_type(MEMORY_TYPE_PRODUCT, organization_id=1)

    assert memory.retrieve_calls == []
    assert memory.search_calls == []


# --- delegation to AgentMemory (never bypassed) ------------------------------------------------


@pytest.mark.parametrize(
    "method_name,builder",
    [
        ("remember_product", lambda: (Product(name="x"),)),
        ("remember_feature", lambda: (FeatureInitiative(title="x"),)),
        ("remember_roadmap", lambda: (RoadmapItem(title="x"),)),
        ("remember_metric", lambda: (Metric(name="x"),)),
        ("remember_discovery", lambda: (DiscoveryFinding(summary="s", source="src"),)),
        ("remember_research", lambda: (ResearchFinding(summary="s", source_question="q"),)),
        ("remember_stakeholder", lambda: (Stakeholder(name="x"),)),
        ("remember_decision", lambda: (_decision_record(),)),
        ("remember_portfolio", lambda: (Portfolio(),)),
    ],
)
def test_every_remember_method_delegates_to_agent_memory_remember(method_name, builder):
    memory = _FakeMemory()
    service = _service(memory=memory)
    getattr(service, method_name)(*builder(), organization_id=1)
    assert len(memory.remembered) == 1


def test_no_remember_method_ever_calls_ai_memory_service_directly():
    # writes always go through AgentMemory.remember() - never a bypass
    # straight to AIMemoryService, even though the service also holds an
    # AIMemoryService reference for its bulk-read path.
    import inspect

    source = inspect.getsource(ProfessionalMemoryService)
    remember_section = source[: source.index("# --- read side")]
    assert "self.memory_service.create_memory" not in remember_section
    assert "self.memory_service." not in remember_section


# --- namespace isolation ------------------------------------------------------------------------


def test_no_remember_method_ever_writes_a_personal_intelligence_memory_type():
    from app.services.ai.agents.specialists.personal_intelligence.shared.types import (
        ALL_MEMORY_TYPES as CP01_TYPES,
    )
    from app.services.ai.agents.specialists.product_management.shared.types import ALL_MEMORY_TYPES as CP02_TYPES

    assert set(CP02_TYPES).isdisjoint(set(CP01_TYPES))


def test_professional_memory_service_and_personal_memory_service_can_share_one_agent_memory_without_collision():
    from app.services.ai.agents.specialists.personal_intelligence.memory_service import PersonalMemoryService
    from app.services.ai.agents.specialists.personal_intelligence.shared.goal import Goal

    memory = _FakeMemory()
    personal_service = PersonalMemoryService(memory)
    professional_service = ProfessionalMemoryService(memory, _FakeMemoryService())

    personal_service.remember_goal(Goal(title="Learn Mandarin"), organization_id=1)
    professional_service.remember_product(Product(name="AI OS"), organization_id=1)

    memory_types_written = {kwargs["memory_type"] for _, kwargs in memory.remembered}
    assert memory_types_written == {"personal_goal", "product_context"}


# --- backward compatibility (this service touches nothing else) --------------------------------


def test_constructing_the_service_does_not_import_personal_intelligence_code():
    # a fresh ProfessionalMemoryService must not import, construct, or
    # otherwise reach into CP-01's own agent/memory-service types - checked
    # against the module's actual import statements (via ast), never a
    # blunt substring match that would also flag this module's own
    # cross-reference comments/docstrings.
    import ast
    import importlib
    import inspect

    module = importlib.import_module("app.services.ai.agents.specialists.product_management.memory_service")
    tree = ast.parse(inspect.getsource(module))
    imported_modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    assert not any("personal_intelligence" in name for name in imported_modules)


# --- malformed entities / missing required values never reach the memory layer ----------------


def test_a_discovery_finding_missing_its_source_cannot_be_constructed_let_alone_remembered():
    with pytest.raises(ValueError, match="source"):
        DiscoveryFinding(summary="s", source="")


def test_a_decision_record_missing_its_counterpoint_cannot_be_constructed_let_alone_remembered():
    with pytest.raises(ValueError, match="counterpoint"):
        _decision_record(counterpoint="")


def test_a_decision_record_missing_supporting_evidence_cannot_be_constructed_let_alone_remembered():
    with pytest.raises(ValueError, match="supporting_memory_ids"):
        _decision_record(supporting_memory_ids=())


def test_a_research_finding_missing_its_source_question_cannot_be_constructed_let_alone_remembered():
    with pytest.raises(ValueError, match="source_question"):
        ResearchFinding(summary="s", source_question="")


# --- immutability preservation ------------------------------------------------------------------


def test_remembering_a_domain_object_never_mutates_it():
    memory = _FakeMemory()
    service = _service(memory=memory)
    product = Product(name="AI OS", owning_pm="Vic")

    service.remember_product(product, organization_id=1)

    assert product.name == "AI OS"
    assert product.owning_pm == "Vic"
    with pytest.raises(AttributeError):
        product.name = "mutated"


def test_remembering_a_decision_record_never_mutates_its_evidence_tuple():
    memory = _FakeMemory()
    service = _service(memory=memory)
    decision = _decision_record(supporting_memory_ids=(1, 2, 3))

    service.remember_decision(decision, organization_id=1)

    assert decision.supporting_memory_ids == (1, 2, 3)
    assert isinstance(decision.supporting_memory_ids, tuple)


# --- edge cases -----------------------------------------------------------------------------


def test_list_by_memory_type_with_a_since_style_old_row_still_included_since_no_cutoff_is_applied():
    # Milestone 2 deliberately has no `since` cutoff on list_by_memory_type
    # (not requested for this milestone) - an old row is still returned.
    old_row = _row(1, memory_type=MEMORY_TYPE_PRODUCT, created_at=datetime.now(UTC) - timedelta(days=3650))
    service = _service(memory_service=_FakeMemoryService([old_row]))

    items = service.list_by_memory_type(MEMORY_TYPE_PRODUCT, organization_id=1)

    assert len(items) == 1


def test_recall_and_search_and_list_by_memory_type_are_independent_read_paths():
    memory = _FakeMemory()
    memory_service = _FakeMemoryService([_row(1, memory_type=MEMORY_TYPE_PRODUCT)])
    service = ProfessionalMemoryService(memory, memory_service)

    service.recall("q", organization_id=1)
    service.search("q", organization_id=1)
    service.list_by_memory_type(MEMORY_TYPE_PRODUCT, organization_id=1)

    assert len(memory.retrieve_calls) == 1
    assert len(memory.search_calls) == 1
    assert len(memory_service.calls) == 1
