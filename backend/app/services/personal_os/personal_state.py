"""PersonalState - what Personal OS currently understands about the user
(§5 of the build spec), assembled by reading CP-01 and CP-02's own
already-written memory content through the existing AgentMemory contract.

This is the Application-layer read path the Application Layer Definition
(VERSION_1_PLATFORM_BASELINE.md) describes: Personal OS never imports
PersonalIntelligenceAgent, any CP-02 specialist, or any of their shared
domain types - it reads the same Memory Framework surface any consumer
reads, filtered by the memory_type string constants CP-01/CP-02 already
publish as their own approved vocabulary (ADR-0006), reproduced here as
plain string literals specifically so this module never has an import
edge to either pack's own code (verified by
test_personal_os_architecture.py).

Only what CP-01/CP-02 already have durable, retrievable content for is
implemented this phase: goals, projects, reflections (CP-01); decisions,
discovery findings, delivery artifacts, roadmap items (CP-02). Messages,
meetings, opportunities, and financial/business intelligence are declared
fields with no data source yet - never populated with invented content,
per "do not fake external integrations."
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.services.ai.agents.memory import AgentMemory
from app.services.ai.agents.specialists.memory_adapter import MemoryAdapter

# CP-01's own approved memory_type constants (personal_intelligence/shared/types.py),
# reproduced as literals - never imported - so this module has no code
# dependency on CP-01's package, only a data dependency on its namespace.
_MEMORY_TYPE_GOAL = "personal_goal"
_MEMORY_TYPE_PROJECT = "personal_project"
_MEMORY_TYPE_REFLECTION = "personal_reflection"

# CP-02's own approved memory_type constants (product_management/shared/types.py),
# reproduced the same way.
_MEMORY_TYPE_DECISION = "product_decision"
_MEMORY_TYPE_DISCOVERY_FINDING = "product_discovery_finding"
_MEMORY_TYPE_DELIVERY_ARTIFACT = "product_delivery_artifact"
_MEMORY_TYPE_ROADMAP = "product_roadmap"

_DEFAULT_LIMIT = 10
_DEFAULT_MAX_CONTEXT_TOKENS = 4000


@dataclass(frozen=True)
class PersonalStateItem:
    """One piece of state Personal OS read from CP-01/CP-02's own
    memory - never re-typed into a Personal-OS-specific shape, since
    Personal OS does not own or reinterpret this content, only surfaces
    it."""

    memory_type: str
    content: str
    resource_id: int
    created_at: datetime


@dataclass(frozen=True)
class PersonalState:
    """Everything Personal OS currently understands, assembled at read
    time - never cached or persisted by this module itself, since it is
    a live view over CP-01/CP-02's own memory, not a new store."""

    goals: tuple[PersonalStateItem, ...] = field(default_factory=tuple)
    projects: tuple[PersonalStateItem, ...] = field(default_factory=tuple)
    reflections: tuple[PersonalStateItem, ...] = field(default_factory=tuple)
    decisions: tuple[PersonalStateItem, ...] = field(default_factory=tuple)
    discovery_findings: tuple[PersonalStateItem, ...] = field(default_factory=tuple)
    delivery_artifacts: tuple[PersonalStateItem, ...] = field(default_factory=tuple)
    roadmap_items: tuple[PersonalStateItem, ...] = field(default_factory=tuple)
    # Declared, not yet sourced (§5, §8) - deliberately empty until a real
    # integration exists; never filled with invented content.
    messages: tuple[PersonalStateItem, ...] = field(default_factory=tuple)
    meetings: tuple[PersonalStateItem, ...] = field(default_factory=tuple)
    opportunities: tuple[PersonalStateItem, ...] = field(default_factory=tuple)
    financial_signals: tuple[PersonalStateItem, ...] = field(default_factory=tuple)

    @property
    def has_active_commitments(self) -> bool:
        return bool(self.goals or self.projects or self.decisions or self.delivery_artifacts)


class PersonalStateReader:
    """Assembles a PersonalState by reading through AgentMemory - the
    same seam MemoryAdapter/ProfessionalMemoryService/PersonalMemoryService
    already use, so a fake is trivial to inject in tests and this reader
    never depends on a concrete adapter."""

    def __init__(self, memory: AgentMemory | None = None) -> None:
        self.memory = memory or MemoryAdapter()

    def read(self, *, organization_id: int, limit: int = _DEFAULT_LIMIT) -> PersonalState:
        return PersonalState(
            goals=self._read(_MEMORY_TYPE_GOAL, organization_id, limit),
            projects=self._read(_MEMORY_TYPE_PROJECT, organization_id, limit),
            reflections=self._read(_MEMORY_TYPE_REFLECTION, organization_id, limit),
            decisions=self._read(_MEMORY_TYPE_DECISION, organization_id, limit),
            discovery_findings=self._read(_MEMORY_TYPE_DISCOVERY_FINDING, organization_id, limit),
            delivery_artifacts=self._read(_MEMORY_TYPE_DELIVERY_ARTIFACT, organization_id, limit),
            roadmap_items=self._read(_MEMORY_TYPE_ROADMAP, organization_id, limit),
        )

    def _read(self, memory_type: str, organization_id: int, limit: int) -> tuple[PersonalStateItem, ...]:
        package = self.memory.retrieve(
            memory_type,
            organization_id=organization_id,
            scope="memories",
            limit=limit,
            max_context_tokens=_DEFAULT_MAX_CONTEXT_TOKENS,
        )
        items = []
        for section in package.sections:
            for context_item in section.items:
                item_memory_type = (context_item.metadata or {}).get("memory_type")
                if item_memory_type is not None and item_memory_type != memory_type:
                    continue
                items.append(
                    PersonalStateItem(
                        memory_type=memory_type,
                        content=context_item.content,
                        resource_id=context_item.resource_id,
                        created_at=context_item.created_at,
                    )
                )
        return tuple(items)
