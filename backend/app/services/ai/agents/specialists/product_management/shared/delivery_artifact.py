"""DeliveryArtifact - drafted specs, stories, acceptance criteria,
launch-readiness state, and other Delivery-owned drafts (Architecture §6).
Added at Milestone 5, per shared/types.py's own documented deferral - this
is Architecture §6's originally-approved tenth and final memory category,
not a new memory-type decision (no ADR required, ARR §4 Ownership Matrix
already assigns it to the Delivery Specialist).

Two fields are required, not optional, tracing to ARR §6's own precise
specification ("must reference the Feature/Initiative and evidence it's
grounded in") and Architecture §14's quality rubric ("a drafted PRD is
incomplete without traceable evidence links"):

- `feature_title`: which Feature/Initiative this artifact belongs to.
- `linked_evidence_ids`: the Discovery Finding / Decision Record memory
  ids that ground it.

A DeliveryArtifact that cannot say which feature it belongs to or what
evidence grounds it is not a drafted artifact this pack is permitted to
construct - the same structural discipline DiscoveryFinding, ResearchFinding,
DecisionRecord, and PMCraftRecord already apply to their own required
fields. ARR §6 also specifies this category is append-only ("a revision is
a new draft entry") - realized by ProfessionalMemoryService.remember_delivery_artifact()
always writing a new entry, never updating one in place, exactly like
every other CP-02 memory category.

Milestone 7 (Stakeholder Communication Specialist) adds one further
`DeliveryArtifactType` member - `COMMUNICATION_DRAFT` - for its own
drafted communications. This is not a new memory category: ARR §3's own
"Writes" field for that specialist is explicit ("drafted communication (a
Delivery-Artifact-shaped record, per §6)"), and Implementation_Plan.md's
own Milestone 7 instruction is equally explicit that no new memory
namespace should be introduced without ADR-0006 justification - reusing
this existing, approved category for a genuinely new *kind* of artifact
(same shape: title, content, a named subject in `feature_title`, and
required evidence) is exactly the minimal, additive extension every prior
milestone's own additions to shared/ already established as this
platform's convention, not a new decision. The `feature_title` field is
reused for whatever named subject a communication is actually about - a
Feature/Initiative, a Product, or the Portfolio itself - never fabricated,
always the caller-supplied subject.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_DELIVERY_ARTIFACT


class DeliveryArtifactType(StrEnum):
    SPEC = "spec"
    USER_STORY = "user_story"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"
    LAUNCH_READINESS = "launch_readiness"
    HANDOFF_NOTE = "handoff_note"
    RETROSPECTIVE = "retrospective"
    RECOMMENDATION = "recommendation"
    COMMUNICATION_DRAFT = "communication_draft"


@dataclass(frozen=True)
class DeliveryArtifact:
    title: str
    artifact_type: DeliveryArtifactType
    content: str
    feature_title: str
    linked_evidence_ids: tuple[int, ...]
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_DELIVERY_ARTIFACT

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("DeliveryArtifact.title is required")
        if not self.content:
            raise ValueError("DeliveryArtifact.content is required")
        if not self.feature_title:
            raise ValueError(
                "DeliveryArtifact.feature_title is required - every artifact must reference the "
                "Feature/Initiative it belongs to (ARR §6)"
            )
        if not isinstance(self.linked_evidence_ids, tuple):
            object.__setattr__(self, "linked_evidence_ids", tuple(self.linked_evidence_ids))
        if not self.linked_evidence_ids:
            raise ValueError(
                "DeliveryArtifact.linked_evidence_ids is required - a drafted artifact must trace to the "
                "Discovery Finding or Decision Record that grounds it (Architecture §14, ARR §6)"
            )

    def to_memory_content(self) -> str:
        ids = ", ".join(str(memory_id) for memory_id in self.linked_evidence_ids)
        return (
            f"Delivery artifact ({self.artifact_type.value}) for {self.feature_title}: {self.title}. "
            f"{self.content} Linked evidence: {ids}."
        )
