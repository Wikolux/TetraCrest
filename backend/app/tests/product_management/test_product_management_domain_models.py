"""CP-02 Milestone 1 domain value objects: Product, FeatureInitiative,
RoadmapItem, Metric, DiscoveryFinding, ResearchFinding, Stakeholder,
DecisionRecord, Portfolio.

Covers: construction, field defaults, validation, tuple coercion,
equality, immutability, memory-type tagging, and to_memory_content()
natural-language rendering - the only "structured storage"/"serialization"
this pack has, since the Memory model has no metadata column (mirroring
CP-01's own precedent, see personal_intelligence/shared/types.py).

The single most important property under test throughout: DecisionRecord,
DiscoveryFinding, and ResearchFinding cannot be constructed without their
required evidence/traceability fields - the structural-enforcement
discipline ARR §7 required, mirroring CP-01.3's own `Insight` type.
"""

import dataclasses

import pytest

from app.services.ai.agents.specialists.product_management.shared.decision_record import (
    DecisionFramework,
    DecisionRecord,
)
from app.services.ai.agents.specialists.product_management.shared.discovery_finding import (
    DiscoveryFinding,
    HypothesisStatus,
)
from app.services.ai.agents.specialists.product_management.shared.feature import FeatureInitiative, FeatureStage
from app.services.ai.agents.specialists.product_management.shared.metric import Metric
from app.services.ai.agents.specialists.product_management.shared.portfolio import Portfolio
from app.services.ai.agents.specialists.product_management.shared.product import Product, ProductLifecycleStage
from app.services.ai.agents.specialists.product_management.shared.research_finding import ResearchFinding
from app.services.ai.agents.specialists.product_management.shared.roadmap import (
    RoadmapHorizon,
    RoadmapItem,
    RoadmapItemStatus,
)
from app.services.ai.agents.specialists.product_management.shared.stakeholder import RaciRole, Stakeholder
from app.services.ai.agents.specialists.product_management.shared.types import (
    ALL_MEMORY_TYPES,
    MEMORY_TYPE_DECISION,
    MEMORY_TYPE_DELIVERY_ARTIFACT,
    MEMORY_TYPE_DISCOVERY_FINDING,
    MEMORY_TYPE_FEATURE,
    MEMORY_TYPE_METRIC,
    MEMORY_TYPE_PM_CRAFT_RECORD,
    MEMORY_TYPE_PRODUCT,
    MEMORY_TYPE_RESEARCH_FINDING,
    MEMORY_TYPE_ROADMAP,
    MEMORY_TYPE_STAKEHOLDER,
)

# --- shared/types.py -------------------------------------------------------------------------


def test_every_memory_type_is_namespaced_with_product_prefix():
    assert all(memory_type.startswith("product_") for memory_type in ALL_MEMORY_TYPES)


def test_all_memory_types_contains_exactly_architecture_6s_ten_originally_approved_categories():
    # Milestone 1's own shared/types.py docstring anticipated exactly this
    # extension: PM Craft Record (Milestone 4) and Delivery Artifact
    # (Milestone 5) were both deliberately left undefined until the
    # specialist that owns each was built - not new memory-type decisions,
    # Architecture §6's own originally-approved ten-category catalogue,
    # now complete.
    assert set(ALL_MEMORY_TYPES) == {
        MEMORY_TYPE_PRODUCT,
        MEMORY_TYPE_FEATURE,
        MEMORY_TYPE_ROADMAP,
        MEMORY_TYPE_METRIC,
        MEMORY_TYPE_DISCOVERY_FINDING,
        MEMORY_TYPE_RESEARCH_FINDING,
        MEMORY_TYPE_DECISION,
        MEMORY_TYPE_STAKEHOLDER,
        MEMORY_TYPE_PM_CRAFT_RECORD,
        MEMORY_TYPE_DELIVERY_ARTIFACT,
    }


def test_no_product_memory_type_collides_with_a_personal_intelligence_one():
    from app.services.ai.agents.specialists.personal_intelligence.shared.types import (
        ALL_MEMORY_TYPES as CP01_MEMORY_TYPES,
    )

    assert set(ALL_MEMORY_TYPES).isdisjoint(set(CP01_MEMORY_TYPES))


# --- Product --------------------------------------------------------------------------------


def test_product_defaults():
    product = Product(name="AI Operating System")
    assert product.customer_segment == ""
    assert product.value_proposition == ""
    assert product.lifecycle_stage == ProductLifecycleStage.IDEA
    assert product.owning_pm == ""
    assert product.memory_type == MEMORY_TYPE_PRODUCT


def test_product_requires_a_name():
    with pytest.raises(ValueError, match="name"):
        Product(name="")


def test_product_lifecycle_stage_has_seven_documented_stages():
    assert {member.value for member in ProductLifecycleStage} == {
        "idea",
        "discovery",
        "building",
        "launched",
        "growth",
        "mature",
        "sunset",
    }


def test_product_is_frozen_and_hashable():
    product = Product(name="x")
    with pytest.raises(AttributeError):
        product.name = "mutated"
    hash(product)


def test_product_equality_is_value_based():
    assert Product(name="x", owning_pm="Vic") == Product(name="x", owning_pm="Vic")
    assert Product(name="x") != Product(name="y")


def test_product_to_memory_content_includes_every_populated_field():
    product = Product(
        name="AI Operating System",
        customer_segment="Product managers",
        value_proposition="Remembers everything",
        lifecycle_stage=ProductLifecycleStage.GROWTH,
        owning_pm="Vic",
    )
    content = product.to_memory_content()
    assert "AI Operating System" in content
    assert "Product managers" in content
    assert "Remembers everything" in content
    assert "growth" in content
    assert "Vic" in content


def test_product_to_memory_content_omits_blank_optional_fields():
    content = Product(name="x").to_memory_content()
    assert "Customer segment" not in content
    assert "Value proposition" not in content
    assert "Owned by" not in content


# --- FeatureInitiative -----------------------------------------------------------------------


def test_feature_defaults():
    feature = FeatureInitiative(title="Async status updates")
    assert feature.problem_addressed == ""
    assert feature.stage == FeatureStage.DISCOVERY
    assert feature.linked_evidence_ids == ()
    assert feature.priority_score is None
    assert feature.memory_type == MEMORY_TYPE_FEATURE


def test_feature_requires_a_title():
    with pytest.raises(ValueError, match="title"):
        FeatureInitiative(title="")


def test_feature_coerces_a_list_of_linked_evidence_ids_to_a_tuple():
    feature = FeatureInitiative(title="x", linked_evidence_ids=[1, 2, 3])
    assert feature.linked_evidence_ids == (1, 2, 3)
    assert isinstance(feature.linked_evidence_ids, tuple)


@pytest.mark.parametrize("score", [-0.01, -100])
def test_feature_rejects_negative_priority_score(score):
    with pytest.raises(ValueError, match="priority_score"):
        FeatureInitiative(title="x", priority_score=score)


@pytest.mark.parametrize("score", [0.0, 8.5, 1000.0])
def test_feature_accepts_non_negative_priority_score(score):
    assert FeatureInitiative(title="x", priority_score=score).priority_score == score


def test_feature_stage_has_four_documented_stages():
    assert {member.value for member in FeatureStage} == {"discovery", "delivery", "shipped", "sunset"}


def test_feature_is_frozen():
    feature = FeatureInitiative(title="x")
    with pytest.raises(AttributeError):
        feature.stage = FeatureStage.SHIPPED


def test_feature_to_memory_content_includes_linked_evidence():
    feature = FeatureInitiative(title="x", linked_evidence_ids=(1, 2), priority_score=5.0, product_name="AI OS")
    content = feature.to_memory_content()
    assert "AI OS" in content
    assert "Priority score: 5" in content
    assert "Linked evidence: 1, 2." in content


def test_feature_to_memory_content_omits_evidence_clause_when_empty():
    assert "Linked evidence" not in FeatureInitiative(title="x").to_memory_content()


# --- RoadmapItem -----------------------------------------------------------------------------


def test_roadmap_item_defaults():
    item = RoadmapItem(title="Ship v1")
    assert item.horizon == RoadmapHorizon.LATER
    assert item.status == RoadmapItemStatus.PLANNED
    assert item.depends_on == ()
    assert item.memory_type == MEMORY_TYPE_ROADMAP


def test_roadmap_item_requires_a_title():
    with pytest.raises(ValueError, match="title"):
        RoadmapItem(title="")


def test_roadmap_item_coerces_a_list_of_dependencies_to_a_tuple():
    item = RoadmapItem(title="x", depends_on=["A", "B"])
    assert item.depends_on == ("A", "B")
    assert isinstance(item.depends_on, tuple)


def test_roadmap_horizon_has_three_documented_values():
    assert {member.value for member in RoadmapHorizon} == {"now", "next", "later"}


def test_roadmap_item_status_has_four_documented_values():
    assert {member.value for member in RoadmapItemStatus} == {"planned", "in_progress", "completed", "cancelled"}


def test_roadmap_item_to_memory_content_includes_dependencies():
    item = RoadmapItem(title="x", depends_on=("CP-01",))
    assert "Depends on: CP-01." in item.to_memory_content()


def test_roadmap_item_to_memory_content_omits_dependency_clause_when_empty():
    assert "Depends on" not in RoadmapItem(title="x").to_memory_content()


# --- Metric ------------------------------------------------------------------------------------


def test_metric_defaults():
    metric = Metric(name="Weekly active PMs")
    assert metric.description == ""
    assert metric.target == ""
    assert metric.is_north_star is False
    assert metric.memory_type == MEMORY_TYPE_METRIC


def test_metric_requires_a_name():
    with pytest.raises(ValueError, match="name"):
        Metric(name="")


def test_metric_to_memory_content_flags_north_star():
    content = Metric(name="x", is_north_star=True).to_memory_content()
    assert "North Star Metric" in content


def test_metric_to_memory_content_omits_north_star_clause_when_false():
    assert "North Star" not in Metric(name="x", is_north_star=False).to_memory_content()


def test_metric_is_hashable():
    hash(Metric(name="x"))


# --- DiscoveryFinding -------------------------------------------------------------------------


def test_discovery_finding_defaults():
    finding = DiscoveryFinding(summary="s", source="5 interviews")
    assert finding.hypothesis == ""
    assert finding.status == HypothesisStatus.UNKNOWN
    assert finding.memory_type == MEMORY_TYPE_DISCOVERY_FINDING


def test_discovery_finding_requires_a_summary():
    with pytest.raises(ValueError, match="summary"):
        DiscoveryFinding(summary="", source="x")


def test_discovery_finding_requires_a_source():
    with pytest.raises(ValueError, match="source"):
        DiscoveryFinding(summary="x", source="")


def test_hypothesis_status_has_three_documented_values():
    assert {member.value for member in HypothesisStatus} == {"unknown", "validated", "invalidated"}


def test_discovery_finding_to_memory_content_includes_hypothesis_and_status():
    finding = DiscoveryFinding(summary="s", source="interviews", hypothesis="h", status=HypothesisStatus.VALIDATED)
    content = finding.to_memory_content()
    assert "h" in content
    assert "validated" in content


def test_discovery_finding_to_memory_content_falls_back_to_status_alone_without_a_hypothesis():
    content = DiscoveryFinding(summary="s", source="interviews").to_memory_content()
    assert "Status: unknown." in content


# --- ResearchFinding --------------------------------------------------------------------------


def test_research_finding_defaults():
    finding = ResearchFinding(summary="s", source_question="q")
    assert finding.implications == ""
    assert finding.memory_type == MEMORY_TYPE_RESEARCH_FINDING


def test_research_finding_requires_a_summary():
    with pytest.raises(ValueError, match="summary"):
        ResearchFinding(summary="", source_question="q")


def test_research_finding_requires_a_source_question():
    with pytest.raises(ValueError, match="source_question"):
        ResearchFinding(summary="s", source_question="")


def test_research_finding_to_memory_content_references_the_source_question():
    finding = ResearchFinding(summary="s", source_question="What do competitors offer?")
    assert "What do competitors offer?" in finding.to_memory_content()


def test_research_finding_to_memory_content_includes_implications_when_present():
    finding = ResearchFinding(summary="s", source_question="q", implications="Differentiation opportunity")
    assert "Differentiation opportunity" in finding.to_memory_content()


# --- Stakeholder -------------------------------------------------------------------------------


def test_stakeholder_defaults():
    stakeholder = Stakeholder(name="Jane")
    assert stakeholder.role_or_interest == ""
    assert stakeholder.raci_role is None
    assert stakeholder.communication_preference == ""
    assert stakeholder.memory_type == MEMORY_TYPE_STAKEHOLDER


def test_stakeholder_requires_a_name():
    with pytest.raises(ValueError, match="name"):
        Stakeholder(name="")


def test_raci_role_has_four_documented_values():
    assert {member.value for member in RaciRole} == {"responsible", "accountable", "consulted", "informed"}


def test_stakeholder_to_memory_content_includes_raci_role_when_set():
    content = Stakeholder(name="x", raci_role=RaciRole.ACCOUNTABLE).to_memory_content()
    assert "accountable" in content


def test_stakeholder_to_memory_content_omits_raci_clause_when_unset():
    assert "RACI" not in Stakeholder(name="x").to_memory_content()


# --- DecisionRecord (structural evidence-enforcement, ARR §7) --------------------------------


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


def test_decision_record_defaults():
    decision = _decision_record()
    assert decision.options_considered == ()
    assert decision.outcome == ""
    assert decision.memory_type == MEMORY_TYPE_DECISION


def test_decision_record_requires_a_title():
    with pytest.raises(ValueError, match="title"):
        _decision_record(title="")


def test_decision_record_requires_a_rationale():
    with pytest.raises(ValueError, match="rationale"):
        _decision_record(rationale="")


def test_decision_record_requires_a_counterpoint():
    with pytest.raises(ValueError, match="counterpoint"):
        _decision_record(counterpoint="")


def test_decision_record_requires_supporting_memory_ids():
    with pytest.raises(ValueError, match="supporting_memory_ids"):
        _decision_record(supporting_memory_ids=())


def test_decision_record_cannot_be_constructed_missing_any_required_field_simultaneously():
    # the compound case: every required field absent at once still fails
    # on the first violation encountered, never silently succeeds.
    with pytest.raises(ValueError):
        DecisionRecord(
            title="", framework=DecisionFramework.RICE, rationale="", counterpoint="", supporting_memory_ids=()
        )


def test_decision_record_coerces_lists_to_tuples():
    decision = _decision_record(supporting_memory_ids=[10, 11], options_considered=["a", "b"])
    assert decision.supporting_memory_ids == (10, 11)
    assert decision.options_considered == ("a", "b")
    assert isinstance(decision.supporting_memory_ids, tuple)
    assert isinstance(decision.options_considered, tuple)


def test_decision_framework_has_six_documented_frameworks():
    assert {member.value for member in DecisionFramework} == {
        "rice",
        "ice",
        "kano",
        "cost_of_delay",
        "build_vs_buy",
        "sunset_checklist",
    }


def test_decision_record_is_frozen_and_hashable():
    decision = _decision_record()
    with pytest.raises(AttributeError):
        decision.outcome = "mutated"
    hash(decision)


def test_decision_record_equality_is_value_based():
    assert _decision_record() == _decision_record()
    assert _decision_record(title="a") != _decision_record(title="b")


def test_decision_record_to_memory_content_includes_framework_rationale_and_counterpoint():
    content = _decision_record().to_memory_content()
    assert "build_vs_buy" in content
    assert "ResearchAgent already exists and is proven" in content
    assert "A dedicated pipeline could be more product-specific" in content
    assert "10, 11" in content


def test_decision_record_to_memory_content_includes_outcome_once_known():
    content = _decision_record(outcome="Shipped; reduced build time by 3 weeks.").to_memory_content()
    assert "Shipped; reduced build time by 3 weeks." in content


def test_decision_record_to_memory_content_omits_outcome_clause_before_its_known():
    assert "Outcome" not in _decision_record().to_memory_content()


def test_decision_record_to_memory_content_includes_options_considered_when_present():
    content = _decision_record(options_considered=("build new", "reuse ResearchAgent")).to_memory_content()
    assert "build new; reuse ResearchAgent" in content


# --- Portfolio (v1 seed, no memory_type by design) --------------------------------------------


def test_portfolio_defaults():
    portfolio = Portfolio()
    assert portfolio.product_names == ()
    assert portfolio.priority_notes == ""


def test_portfolio_coerces_a_list_of_product_names_to_a_tuple():
    portfolio = Portfolio(product_names=["A", "B"])
    assert portfolio.product_names == ("A", "B")
    assert isinstance(portfolio.product_names, tuple)


def test_portfolio_has_no_memory_type_by_design():
    # Architecture §12 / ARR §4: Portfolio shares its owner with Roadmap
    # State and is not itself a separately-persisted memory category.
    assert not hasattr(Portfolio, "memory_type")


def test_portfolio_has_no_to_memory_content_by_design():
    assert not hasattr(Portfolio(), "to_memory_content")


def test_portfolio_is_frozen_and_hashable():
    portfolio = Portfolio(product_names=("A",))
    with pytest.raises(AttributeError):
        portfolio.priority_notes = "mutated"
    hash(portfolio)


def test_portfolio_equality_is_value_based():
    assert Portfolio(product_names=("A", "B")) == Portfolio(product_names=("A", "B"))
    assert Portfolio(product_names=("A",)) != Portfolio(product_names=("B",))


# --- cross-cutting: every domain model is a frozen dataclass ---------------------------------


@pytest.mark.parametrize(
    "cls",
    [Product, FeatureInitiative, RoadmapItem, Metric, DiscoveryFinding, ResearchFinding, Stakeholder, DecisionRecord, Portfolio],
)
def test_every_domain_model_is_a_frozen_dataclass(cls):
    assert dataclasses.is_dataclass(cls)
    assert cls.__dataclass_params__.frozen is True
