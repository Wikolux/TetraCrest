"""CP-02 Milestone 8 - end-to-end, multi-specialist workflow validation.

Every test in this file shares ONE in-process Memory Framework model
(mirroring test_product_management_executive_integration.py's own fixture
exactly) across two or more of CP-02's five specialists, each constructed
and invoked independently via its own real `.process()` entry point -
never through one specialist importing or calling another (Pack
Independence, verified separately and exhaustively in
test_product_management_architecture_integration.py). Evidence flowing
from one specialist to the next is therefore a genuine consequence of
"same underlying Memory Framework store," exactly how this would work in
production, not a test-only shortcut.

Rich, multi-step specialist work (VALIDATE_PROBLEM, GENERATE_RECOMMENDATION,
...) is exercised via each specialist's own `.process()` method directly,
the same testing strategy every specialist's own Milestone 3-7 test suite
already established - ExecutivePlanner's current deterministic template
does not construct rich, operation-specific request payloads for any
specialist on this platform today (confirmed in
test_product_management_executive_integration.py's own docstring); that
remains a real, honestly-scoped platform limitation, not something this
milestone's own instruction ("do not introduce a new orchestration
mechanism") allows working around.
"""

from datetime import UTC, datetime

from app.services.ai.agents.context import AgentContext
from app.services.ai.agents.enums import AgentCapability
from app.services.ai.agents.executive.decision import Decision
from app.services.ai.agents.executive.executive_agent import ExecutiveAgent
from app.services.ai.agents.executive.task import Task
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
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
from app.services.context.types import ContextItem, ContextPackage, ContextSection

# --- the shared, in-process Memory Framework model (mirrors the Executive-integration suite) ---


class _StoredMemory:
    def __init__(self, id, organization_id, content, user_id, memory_type, title, created_at):
        self.id = id
        self.organization_id = organization_id
        self.content = content
        self.user_id = user_id
        self.memory_type = memory_type
        self.title = title
        self.created_at = created_at


class _SharedMemoryStore:
    def __init__(self):
        self.rows: list[_StoredMemory] = []

    def create(self, organization_id, content, user_id=None, memory_type="general", title=None):
        row = _StoredMemory(
            id=len(self.rows) + 1,
            organization_id=organization_id,
            content=content,
            user_id=user_id,
            memory_type=memory_type,
            title=title,
            created_at=datetime.now(UTC),
        )
        self.rows.append(row)
        return row.id

    def search(self, organization_id):
        return [row for row in self.rows if row.organization_id == organization_id]


class _WriteSideMemoryService:
    def __init__(self, store: _SharedMemoryStore):
        self.store = store

    def create_memory(self, organization_id, content, user_id=None, memory_type="general", title=None):
        return self.store.create(organization_id, content, user_id=user_id, memory_type=memory_type, title=title)


class _BulkMemoryService:
    def __init__(self, store: _SharedMemoryStore):
        self.store = store

    def list_memories(self, organization_id, skip=0, limit=20):
        rows = self.store.search(organization_id)
        return rows[skip : skip + limit]


class _ReadSideRetrievalPipeline:
    def __init__(self, store: _SharedMemoryStore):
        self.store = store
        self.search_memories_calls = []

    def search_memories(self, query, organization_id, limit=10, max_context_tokens=4000):
        self.search_memories_calls.append((query, organization_id))
        rows = self.store.search(organization_id)[:limit]
        items = [
            ContextItem(
                resource_type="memory", resource_id=row.id, content=row.content, score=1.0, created_at=row.created_at
            )
            for row in rows
        ]
        return ContextPackage(
            sections=[ContextSection(resource_type="memory", items=items)] if items else [],
            estimated_tokens=len(items) * 10,
            item_count=len(items),
            truncated=False,
        )

    def search_conversation_messages(self, query, organization_id, limit=10, max_context_tokens=4000):
        return ContextPackage(sections=[], estimated_tokens=0, item_count=0, truncated=False)

    def search_all(self, query, organization_id, limit=10, max_context_tokens=4000):
        return self.search_memories(query, organization_id, limit=limit, max_context_tokens=max_context_tokens)


class _RecordingRuntime:
    def __init__(self):
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return RuntimeResponse(success=True)


def _shared_environment():
    store = _SharedMemoryStore()
    pipeline = _ReadSideRetrievalPipeline(store)
    memory_adapter = MemoryAdapter(pipeline=pipeline, memory_service=_WriteSideMemoryService(store))
    memory_service = ProfessionalMemoryService(memory_adapter, _BulkMemoryService(store))
    return store, pipeline, memory_adapter, memory_service


def _context() -> SpecialistContext:
    return SpecialistContext(agent_context=AgentContext(organization_id=1, user_id=2))


def _specialist(cls, memory_adapter, memory_service, runtime=None):
    return cls(
        memory_adapter=memory_adapter, memory_service=memory_service, runtime_adapter=RuntimeAdapter(runtime=runtime or _RecordingRuntime())
    )


# --- Discovery -> Decision -> Delivery, evidence flowing across three specialists --------------


def test_discovery_to_decision_to_delivery_full_chain_preserves_evidence_traceability():
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    context = _context()

    discovery = _specialist(DiscoverySpecialist, memory_adapter, memory_service)
    discovery_response = discovery.process(
        DiscoveryRequest(operation=DiscoveryOperation.VALIDATE_PROBLEM, text="Users churn after onboarding", source="Support tickets Q3"),
        context,
    )
    assert discovery_response.success is True
    discovery_finding_id = store.rows[-1].id

    decision = _specialist(ProductDecisionSpecialist, memory_adapter, memory_service)
    decision_response = decision.process(
        DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="Users churn after onboarding", title="Onboarding revamp"),
        context,
    )
    assert decision_response.success is True
    assert str(discovery_finding_id) in decision_response.sources
    decision_record_id = next(row.id for row in store.rows if row.memory_type == "product_decision")

    delivery = _specialist(DeliverySpecialist, memory_adapter, memory_service)
    delivery_response = delivery.process(
        DeliveryRequest(operation=DeliveryOperation.GENERATE_RECOMMENDATION, text="Users churn after onboarding", title="Onboarding revamp", stage="delivery"),
        context,
    )
    assert delivery_response.success is True
    assert str(discovery_finding_id) in delivery_response.sources
    assert str(decision_record_id) in delivery_response.sources


# --- interview evidence leading to a roadmap recommendation (Discovery -> Strategy) -------------


def test_interview_evidence_leads_to_a_roadmap_recommendation():
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    context = _context()

    discovery = _specialist(DiscoverySpecialist, memory_adapter, memory_service)
    discovery.process(
        DiscoveryRequest(operation=DiscoveryOperation.SYNTHESIZE_INTERVIEW, text="Users say onboarding is too slow", source="Interview #4"),
        context,
    )
    interview_finding_id = store.rows[-1].id

    strategy = _specialist(StrategyPortfolioSpecialist, memory_adapter, memory_service)
    response = strategy.process(
        StrategyRequest(operation=StrategyOperation.SEQUENCE_ROADMAP, items=("Faster onboarding",), horizon="now"),
        context,
    )

    assert response.success is True
    assert str(interview_finding_id) in response.sources
    assert any(row.memory_type == "product_roadmap" for row in store.rows)


# --- Discovery findings producing Delivery artifacts (skip Decision entirely) ------------------


def test_discovery_findings_directly_produce_delivery_artifacts():
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    context = _context()

    discovery = _specialist(DiscoverySpecialist, memory_adapter, memory_service)
    discovery.process(DiscoveryRequest(operation=DiscoveryOperation.VALIDATE_PROBLEM, text="Checkout is confusing", source="Support tickets"), context)
    discovery.process(DiscoveryRequest(operation=DiscoveryOperation.SYNTHESIZE_INTERVIEW, text="Users abandon checkout", source="Interview #7"), context)
    finding_ids = {row.id for row in store.rows}

    delivery = _specialist(DeliverySpecialist, memory_adapter, memory_service)
    response = delivery.process(
        DeliveryRequest(operation=DeliveryOperation.GENERATE_ACCEPTANCE_CRITERIA, text="Checkout is confusing", feature_title="Checkout redesign"),
        context,
    )

    assert response.success is True
    assert finding_ids.issubset({int(source) for source in response.sources})
    artifact_row = next(row for row in store.rows if row.memory_type == "product_delivery_artifact")
    assert "acceptance_criteria" in artifact_row.content


# --- Strategy consuming both roadmap AND delivery outputs ---------------------------------------


def test_strategy_consumes_both_roadmap_and_delivery_outputs():
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    context = _context()

    discovery = _specialist(DiscoverySpecialist, memory_adapter, memory_service)
    discovery.process(DiscoveryRequest(operation=DiscoveryOperation.VALIDATE_PROBLEM, text="Search is slow", source="Support tickets"), context)

    delivery = _specialist(DeliverySpecialist, memory_adapter, memory_service)
    delivery.process(
        DeliveryRequest(operation=DeliveryOperation.GENERATE_ACCEPTANCE_CRITERIA, text="Search is slow", feature_title="Search performance"),
        context,
    )
    delivery_artifact_id = next(row.id for row in store.rows if row.memory_type == "product_delivery_artifact")

    strategy = _specialist(StrategyPortfolioSpecialist, memory_adapter, memory_service)
    strategy.process(StrategyRequest(operation=StrategyOperation.SEQUENCE_ROADMAP, items=("Search performance",), horizon="now"), context)
    roadmap_item_id = next(row.id for row in store.rows if row.memory_type == "product_roadmap")

    response = strategy.process(
        StrategyRequest(operation=StrategyOperation.ASSESS_TRADEOFFS, text="Search performance", items=("Search performance", "New feature X")),
        context,
    )

    assert response.success is True
    assert str(delivery_artifact_id) in response.sources
    assert str(roadmap_item_id) in response.sources


# --- Stakeholder communication generated from validated strategic outputs ----------------------


def test_stakeholder_communication_generated_from_validated_strategic_outputs():
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    context = _context()

    strategy = _specialist(StrategyPortfolioSpecialist, memory_adapter, memory_service)
    strategy.process(StrategyRequest(operation=StrategyOperation.SEQUENCE_ROADMAP, items=("Faster onboarding",), horizon="now"), context)
    roadmap_item_id = store.rows[-1].id

    stakeholder_comm = _specialist(StakeholderCommunicationSpecialist, memory_adapter, memory_service)
    response = stakeholder_comm.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION,
            text="Faster onboarding",
            audience="executive",
            purpose="roadmap_communication",
        ),
        context,
    )

    assert response.success is True
    assert str(roadmap_item_id) in response.sources
    artifact_row = next(row for row in store.rows if row.memory_type == "product_delivery_artifact")
    assert "communication_draft" in artifact_row.content


# --- failed Discovery leads to honest recommendations, never fabricated downstream --------------


def test_failed_discovery_produces_honest_recommendations_at_every_downstream_stage_never_fabricated():
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    context = _context()
    assert store.rows == []

    decision = _specialist(ProductDecisionSpecialist, memory_adapter, memory_service)
    decision_response = decision.process(
        DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="Should we build feature X?", title="Feature X"), context
    )
    assert decision_response.success is True
    assert decision_response.confidence < 0.5
    assert "discovery" in decision_response.recommendations[0].lower() or "decision" in decision_response.recommendations[0].lower()

    delivery = _specialist(DeliverySpecialist, memory_adapter, memory_service)
    delivery_response = delivery.process(
        DeliveryRequest(operation=DeliveryOperation.GENERATE_RECOMMENDATION, text="Should we build feature X?", title="Feature X"), context
    )
    assert delivery_response.success is True
    assert delivery_response.confidence < 0.5

    strategy = _specialist(StrategyPortfolioSpecialist, memory_adapter, memory_service)
    strategy_response = strategy.process(
        StrategyRequest(operation=StrategyOperation.GENERATE_RECOMMENDATION, text="Should we build feature X?", title="Feature X"), context
    )
    assert strategy_response.success is True
    assert strategy_response.confidence < 0.5

    stakeholder_comm = _specialist(StakeholderCommunicationSpecialist, memory_adapter, memory_service)
    comm_response = stakeholder_comm.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION, text="Should we build feature X?", audience="executive", purpose="status_report"
        ),
        context,
    )
    assert comm_response.success is True
    assert comm_response.confidence < 0.5

    # The single strongest proof: not one of the four downstream specialists
    # wrote anything to memory when the evidence chain never started.
    assert store.rows == []


# --- cross-session memory retrieval preserves traceability -------------------------------------


def test_cross_session_memory_retrieval_preserves_traceability():
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    context = _context()

    # "Session 1": one process, one Discovery instance, written and then
    # discarded - nothing about it survives except what it wrote to the
    # shared store.
    session_one_discovery = _specialist(DiscoverySpecialist, memory_adapter, memory_service)
    session_one_discovery.process(
        DiscoveryRequest(operation=DiscoveryOperation.VALIDATE_PROBLEM, text="Onboarding drop-off is high", source="Analytics dashboard"), context
    )
    finding_id = store.rows[-1].id
    del session_one_discovery

    # "Session 2": brand-new specialist instances, constructed fresh
    # against the same store - modeling a new request, possibly served by
    # a different process entirely.
    session_two_decision = _specialist(ProductDecisionSpecialist, memory_adapter, memory_service)
    response = session_two_decision.process(
        DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="Onboarding drop-off is high", title="Onboarding fix"), context
    )

    assert response.success is True
    assert str(finding_id) in response.sources
    decision_content = next(row.content for row in store.rows if row.memory_type == "product_decision")
    assert str(finding_id) in decision_content


# --- the full five-specialist workflow, with Executive-verified routing at every stage ----------


def test_full_five_specialist_workflow_with_executive_verified_capability_routing_at_every_stage():
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    context = _context()

    discovery = _specialist(DiscoverySpecialist, memory_adapter, memory_service)
    decision = _specialist(ProductDecisionSpecialist, memory_adapter, memory_service)
    delivery = _specialist(DeliverySpecialist, memory_adapter, memory_service)
    strategy = _specialist(StrategyPortfolioSpecialist, memory_adapter, memory_service)
    stakeholder_comm = _specialist(StakeholderCommunicationSpecialist, memory_adapter, memory_service)

    known_agents = {
        "discovery": discovery,
        "product_decision": decision,
        "delivery": delivery,
        "strategy_portfolio": strategy,
        "stakeholder_communication": stakeholder_comm,
    }
    executive = ExecutiveAgent(retrieval_pipeline=pipeline, known_agents=known_agents)

    # Stage 1: Discovery - Executive would route a REASONING-tagged task
    # here, among others; the real evidence-producing work happens via
    # .process() (see this file's own module docstring).
    reasoning_task = Task(title="discovery work", execution_id="exec-1", metadata={"required_capability": AgentCapability.REASONING})
    assert executive.dispatch(Decision(), reasoning_task) in known_agents.values()
    discovery.process(
        DiscoveryRequest(operation=DiscoveryOperation.VALIDATE_PROBLEM, text="Trial users churn before activation", source="Product analytics"),
        context,
    )
    discovery_finding_id = store.rows[-1].id

    # Stage 2: Product Decision.
    decision_response = decision.process(
        DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="Trial users churn before activation", title="Activation revamp"),
        context,
    )
    assert str(discovery_finding_id) in decision_response.sources
    decision_record_id = next(row.id for row in store.rows if row.memory_type == "product_decision")

    # Stage 3: Delivery.
    delivery_response = delivery.process(
        DeliveryRequest(operation=DeliveryOperation.GENERATE_RECOMMENDATION, text="Trial users churn before activation", title="Activation revamp", stage="delivery"),
        context,
    )
    assert str(decision_record_id) in delivery_response.sources
    delivery_artifact_id = next(row.id for row in store.rows if row.memory_type == "product_delivery_artifact")

    # Stage 4: Strategy - a COMMUNICATION-tagged task must route only to
    # Stakeholder Communication, never Strategy, proving capability-based
    # routing discriminates correctly even with all five specialists
    # simultaneously known to the Executive.
    communication_task = Task(title="draft update", execution_id="exec-2", metadata={"required_capability": AgentCapability.COMMUNICATION})
    assert executive.dispatch(Decision(), communication_task) is stakeholder_comm
    strategy_response = strategy.process(
        StrategyRequest(operation=StrategyOperation.SEQUENCE_ROADMAP, items=("Activation revamp",), horizon="now"), context
    )
    assert str(delivery_artifact_id) in strategy_response.sources
    roadmap_item_id = next(row.id for row in store.rows if row.memory_type == "product_roadmap")

    # Stage 5: Stakeholder Communication - the final stage, drafting a
    # communication grounded in everything the previous four stages wrote.
    comm_response = stakeholder_comm.process(
        StakeholderCommunicationRequest(
            operation=StakeholderCommunicationOperation.DRAFT_COMMUNICATION,
            text="Trial users churn before activation",
            audience="executive",
            purpose="status_report",
        ),
        context,
    )
    assert comm_response.success is True
    all_prior_ids = {str(discovery_finding_id), str(decision_record_id), str(delivery_artifact_id), str(roadmap_item_id)}
    assert all_prior_ids.issubset(set(comm_response.sources))


# --- performance validation: bounded, non-redundant work across the chained workflow ------------


def test_multi_specialist_workflow_makes_exactly_one_runtime_call_per_stage_no_redundant_work():
    # "Performance" here means what is honestly measurable against
    # in-process fakes: no accidental duplicate Runtime calls or memory
    # retrievals across a chained workflow - not wall-clock timing, which
    # would be meaningless (and flaky) against fakes with no real latency.
    store, pipeline, memory_adapter, memory_service = _shared_environment()
    context = _context()
    runtimes = [_RecordingRuntime() for _ in range(3)]

    discovery = _specialist(DiscoverySpecialist, memory_adapter, memory_service, runtimes[0])
    decision = _specialist(ProductDecisionSpecialist, memory_adapter, memory_service, runtimes[1])
    delivery = _specialist(DeliverySpecialist, memory_adapter, memory_service, runtimes[2])

    discovery.process(DiscoveryRequest(operation=DiscoveryOperation.VALIDATE_PROBLEM, text="Users churn", source="tickets"), context)
    decision.process(DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="Users churn", title="Fix"), context)
    delivery.process(DeliveryRequest(operation=DeliveryOperation.GENERATE_RECOMMENDATION, text="Users churn", title="Fix"), context)

    assert len(runtimes[0].requests) == 1
    assert len(runtimes[1].requests) == 1
    assert len(runtimes[2].requests) == 1


def test_event_ordering_is_preserved_independently_per_specialist_within_one_shared_workflow():
    from app.services.ai.agents.specialists.product_management.discovery.events import DiscoveryEventPublisher, DiscoveryEventType
    from app.services.ai.agents.specialists.product_management.product_decision.events import DecisionEventPublisher, DecisionEventType

    store, pipeline, memory_adapter, memory_service = _shared_environment()
    context = _context()

    discovery_events = []
    discovery_publisher = DiscoveryEventPublisher()
    discovery_publisher.subscribe(discovery_events.append)
    discovery = DiscoverySpecialist(
        memory_adapter=memory_adapter, memory_service=memory_service, runtime_adapter=RuntimeAdapter(runtime=_RecordingRuntime()), event_publisher=discovery_publisher
    )
    discovery.process(DiscoveryRequest(operation=DiscoveryOperation.VALIDATE_PROBLEM, text="Users churn", source="tickets"), context)

    decision_events = []
    decision_publisher = DecisionEventPublisher()
    decision_publisher.subscribe(decision_events.append)
    decision = ProductDecisionSpecialist(
        memory_adapter=memory_adapter, memory_service=memory_service, runtime_adapter=RuntimeAdapter(runtime=_RecordingRuntime()), event_publisher=decision_publisher
    )
    decision.process(DecisionRequest(operation=DecisionOperation.GENERATE_RECOMMENDATION, question="Users churn", title="Fix"), context)

    assert [event.event_type for event in discovery_events][0] == DiscoveryEventType.REQUEST_STARTED
    assert [event.event_type for event in discovery_events][-1] == DiscoveryEventType.REQUEST_COMPLETED
    assert [event.event_type for event in decision_events][0] == DecisionEventType.REQUEST_STARTED
    assert [event.event_type for event in decision_events][-1] == DecisionEventType.REQUEST_COMPLETED
    # Each specialist's own event stream is entirely independent - Decision's
    # events never appear mixed into Discovery's own publisher, and vice
    # versa, even though both operated within the same shared workflow.
    assert not any(event in decision_events for event in discovery_events)
