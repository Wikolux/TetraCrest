"""Shared, pack-local leaf types for the Product Management Intelligence
Pack (CP-02) - the Metadata alias every dataclass in this pack uses, and
the memory_type tag constants that categorize every Memory row this pack
writes.

Every memory_type value is namespaced with a "product_" prefix,
deliberately mirroring CP-01's own "personal_" convention (see
personal_intelligence/shared/types.py) - the same discipline, applied to
CP-02's own domain, so CP-02's categories can never collide with CP-01's,
or with any future pack's. See
docs/08_CAPABILITY_PACKS/CP-02_Product_Management_Intelligence_Pack/Architecture.md
§6 for the full, approved category catalogue this constant set realizes.

These are categorization *conventions* layered on the Memory Framework's
existing, unmodified `memory_type: str` field - not a new schema, not a
new table, not a new storage mechanism (Architecture §5's own governing
constraint, unchanged by this milestone).

Milestone 1 defined only the eight categories the domain models built in
that milestone actually used. Two more categories named in Architecture §6
- Delivery Artifact and PM Craft Record - were deliberately left undefined
until the specialist that owns each was actually built (Implementation_Plan.md,
Milestones 5 and 4 respectively), mirroring exactly how CP-01's own
shared/types.py grew a sixth memory type only once CP-01.3's Insight
Engine needed one. Milestone 4 (Product Decision Specialist) added MEMORY_TYPE_PM_CRAFT_RECORD
- already an approved category in Architecture §6's original ten-category
catalogue and ARR §4's Ownership Matrix ("Career Knowledge (PM Craft
Record) - CP-02 - Product Decision Specialist - byproduct of Decision
Support, per Architecture §13"), not a new memory-type decision requiring
an ADR. Milestone 5 (Delivery Specialist) now adds the tenth and final
category from that same original catalogue, MEMORY_TYPE_DELIVERY_ARTIFACT
- ARR §4's Ownership Matrix assigns "Delivery Artifacts" to the Delivery
Specialist, and ARR §6 further specifies it "must reference the
Feature/Initiative and evidence it's grounded in." Every category
Architecture §6 originally approved is now defined.
"""

from typing import Any, Mapping

Metadata = Mapping[str, Any]

MEMORY_TYPE_PRODUCT = "product_context"
MEMORY_TYPE_FEATURE = "product_feature"
MEMORY_TYPE_ROADMAP = "product_roadmap"
MEMORY_TYPE_METRIC = "product_metric"
MEMORY_TYPE_DISCOVERY_FINDING = "product_discovery_finding"
MEMORY_TYPE_RESEARCH_FINDING = "product_research_finding"
MEMORY_TYPE_DECISION = "product_decision"
MEMORY_TYPE_STAKEHOLDER = "product_stakeholder"
MEMORY_TYPE_PM_CRAFT_RECORD = "product_pm_craft_record"
MEMORY_TYPE_DELIVERY_ARTIFACT = "product_delivery_artifact"

ALL_MEMORY_TYPES = (
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
)
