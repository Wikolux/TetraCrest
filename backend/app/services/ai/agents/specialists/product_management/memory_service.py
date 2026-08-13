"""ProfessionalMemoryService - CP-02's single memory gateway, exactly the
role PersonalMemoryService plays for CP-01
(personal_intelligence/memory_service.py). Every future CP-02 specialist
(Discovery, Delivery, Product Decision, Strategy & Portfolio, Stakeholder
Communication) reads and writes Professional Memory exclusively through
this service - never through AgentMemory directly, and never through a
private, specialist-local write path.

Never reimplements storage or retrieval: every remember_*() method does
exactly one thing - render a CP-02 domain object to natural-language
memory content (each object's own to_memory_content(), already written
for semantic retrievability, per Milestone 1) and call
AgentMemory.remember() with it, tagged with that object's own approved
product_* memory_type (Milestone 1's shared/types.py - no new category is
ever introduced here, per Implementation_Plan.md §7).

Two read paths, mirroring InsightMemoryService's own precedent exactly
(personal_intelligence/insight/memory_service.py):

1. recall()/search() go through AgentMemory.retrieve()/.search() -
   semantic, relevance-ranked, PromptBuilder-ready ContextPackage, via
   the existing MemoryRetrievalPipeline. Both are exposed, mirroring
   AgentMemory's own two-method surface, rather than one being sugar for
   the other - MemoryAdapter's own choice of how search relates to
   retrieve stays entirely encapsulated there.
2. list_by_memory_type() goes through AIMemoryService.list_memories() -
   bulk, paginated, unmodified - filtering by memory_type client-side,
   since the platform's retrieval layer has no type-filtered query and
   this milestone does not add one (Architecture §5's own governing
   constraint, restated for CP-02 in Architecture §5/ARR §6).

Defaults to constructing a MemoryAdapter (the platform's only concrete
AgentMemory) and a bare AIMemoryService, but is typed against AgentMemory
itself so a fake is trivial to inject in tests - the same reasoning
already applied to SpecialistCoordinator.memory_adapter and to every
other CP-01/CP-01.3 memory service.
"""

from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter
from app.services.ai.agents.specialists.product_management.shared.decision_record import DecisionRecord
from app.services.ai.agents.specialists.product_management.shared.delivery_artifact import DeliveryArtifact
from app.services.ai.agents.specialists.product_management.shared.discovery_finding import DiscoveryFinding
from app.services.ai.agents.specialists.product_management.shared.feature import FeatureInitiative
from app.services.ai.agents.specialists.product_management.shared.metric import Metric
from app.services.ai.agents.specialists.product_management.shared.pm_craft_record import PMCraftRecord
from app.services.ai.agents.specialists.product_management.shared.portfolio import Portfolio
from app.services.ai.agents.specialists.product_management.shared.product import Product
from app.services.ai.agents.specialists.product_management.shared.research_finding import ResearchFinding
from app.services.ai.agents.specialists.product_management.shared.roadmap import RoadmapItem
from app.services.ai.agents.specialists.product_management.shared.stakeholder import Stakeholder
from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_ROADMAP
from app.services.ai_memory_service import AIMemoryService
from app.services.context.types import ContextItem, ContextPackage

_DEFAULT_LIMIT = 10
_DEFAULT_MAX_CONTEXT_TOKENS = 4000
_DEFAULT_LIST_MAXIMUM = 200
_DEFAULT_PAGE_SIZE = 100


class ProfessionalMemoryService:
    def __init__(self, memory: AgentMemory | None = None, memory_service: AIMemoryService | None = None) -> None:
        self.memory = memory or MemoryAdapter()
        self.memory_service = memory_service or AIMemoryService()

    # --- write side ----------------------------------------------------------------------

    def remember_product(self, product: Product, *, organization_id: int, user_id: int | None = None) -> None:
        self._remember(product.to_memory_content(), product.memory_type, product.name, organization_id, user_id)

    def remember_feature(self, feature: FeatureInitiative, *, organization_id: int, user_id: int | None = None) -> None:
        self._remember(feature.to_memory_content(), feature.memory_type, feature.title, organization_id, user_id)

    def remember_roadmap(self, item: RoadmapItem, *, organization_id: int, user_id: int | None = None) -> None:
        self._remember(item.to_memory_content(), item.memory_type, item.title, organization_id, user_id)

    def remember_metric(self, metric: Metric, *, organization_id: int, user_id: int | None = None) -> None:
        self._remember(metric.to_memory_content(), metric.memory_type, metric.name, organization_id, user_id)

    def remember_discovery(self, finding: DiscoveryFinding, *, organization_id: int, user_id: int | None = None) -> None:
        title = f"Discovery finding ({finding.status.value})"
        self._remember(finding.to_memory_content(), finding.memory_type, title, organization_id, user_id)

    def remember_research(self, finding: ResearchFinding, *, organization_id: int, user_id: int | None = None) -> None:
        title = f"Research finding: {finding.source_question}"
        self._remember(finding.to_memory_content(), finding.memory_type, title, organization_id, user_id)

    def remember_stakeholder(self, stakeholder: Stakeholder, *, organization_id: int, user_id: int | None = None) -> None:
        self._remember(
            stakeholder.to_memory_content(), stakeholder.memory_type, stakeholder.name, organization_id, user_id
        )

    def remember_decision(self, decision: DecisionRecord, *, organization_id: int, user_id: int | None = None) -> None:
        self._remember(decision.to_memory_content(), decision.memory_type, decision.title, organization_id, user_id)

    def remember_craft_record(self, record: PMCraftRecord, *, organization_id: int, user_id: int | None = None) -> None:
        self._remember(
            record.to_memory_content(), record.memory_type, f"Craft record: {record.decision_title}", organization_id, user_id
        )

    def remember_delivery_artifact(
        self, artifact: DeliveryArtifact, *, organization_id: int, user_id: int | None = None
    ) -> None:
        self._remember(artifact.to_memory_content(), artifact.memory_type, artifact.title, organization_id, user_id)

    def remember_portfolio(self, portfolio: Portfolio, *, organization_id: int, user_id: int | None = None) -> None:
        """Portfolio deliberately has no memory_type or to_memory_content()
        of its own (Milestone 1: Architecture §12 / ARR §4 - a Portfolio
        shares its owner with Roadmap State; it is never a separate memory
        category). This method does not introduce a new product_* type to
        work around that - it records the portfolio-level view under the
        already-approved product_roadmap category, exactly the ownership
        Architecture already assigned it, composing its own natural-
        language content here since the domain object deliberately has
        none of its own to delegate to."""
        products = ", ".join(portfolio.product_names) if portfolio.product_names else "no products yet"
        content = f"Portfolio: {products}."
        if portfolio.priority_notes:
            content = f"{content} {portfolio.priority_notes}"
        self._remember(content, MEMORY_TYPE_ROADMAP, "Portfolio snapshot", organization_id, user_id)

    def _remember(self, content: str, memory_type: str, title: str, organization_id: int, user_id: int | None) -> None:
        self.memory.remember(
            content, organization_id=organization_id, user_id=user_id, memory_type=memory_type, title=title
        )

    # --- read side, relevance-ranked: reuses MemoryRetrievalPipeline via AgentMemory ---------

    def recall(
        self,
        query: str,
        *,
        organization_id: int,
        limit: int = _DEFAULT_LIMIT,
        max_context_tokens: int = _DEFAULT_MAX_CONTEXT_TOKENS,
    ) -> ContextPackage:
        return self.memory.retrieve(
            query, organization_id=organization_id, scope="memories", limit=limit, max_context_tokens=max_context_tokens
        )

    def search(
        self,
        query: str,
        *,
        organization_id: int,
        limit: int = _DEFAULT_LIMIT,
        max_context_tokens: int = _DEFAULT_MAX_CONTEXT_TOKENS,
    ) -> ContextPackage:
        return self.memory.search(
            query, organization_id=organization_id, scope="memories", limit=limit, max_context_tokens=max_context_tokens
        )

    # --- read side, bulk, type-scoped: reuses AIMemoryService.list_memories(), unmodified ----

    def list_by_memory_type(
        self, memory_type: str, *, organization_id: int, maximum: int = _DEFAULT_LIST_MAXIMUM
    ) -> tuple[ContextItem, ...]:
        """Every memory of exactly one product_* category for this
        organization - paginated through AIMemoryService.list_memories()
        (unmodified), filtering by memory_type client-side. This is
        deliberately not AgentMemory.retrieve()/.search() (semantic,
        query-scoped) - a caller asking "list everything of type X" needs
        the actual corpus, not a relevance-ranked slice of it for one
        query, the identical reasoning CP-01.3's InsightMemoryService
        already established for its own bulk corpus-gathering need."""
        rows = []
        skip = 0
        page_size = min(maximum, _DEFAULT_PAGE_SIZE) or _DEFAULT_PAGE_SIZE
        while len(rows) < maximum:
            batch = self.memory_service.list_memories(organization_id, skip=skip, limit=page_size)
            if not batch:
                break
            rows.extend(batch)
            skip += page_size
            if len(batch) < page_size:
                break

        items = [
            ContextItem(
                resource_type="memory",
                resource_id=row.id,
                content=row.content,
                score=1.0,
                created_at=row.created_at,
                metadata={"memory_type": row.memory_type, "title": row.title or ""},
            )
            for row in rows
            if row.memory_type == memory_type
        ]
        return tuple(items[:maximum])
