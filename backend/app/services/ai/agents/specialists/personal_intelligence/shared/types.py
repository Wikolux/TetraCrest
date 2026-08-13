"""Shared, pack-local leaf types for the Personal Intelligence Pack
(CP-01) - the Metadata alias every dataclass in this pack uses, and the
memory_type tag constants that categorize every Memory row this pack
writes.

Every memory_type value is namespaced with a "personal_" prefix
deliberately - CP-01 is the first Capability Pack, and future packs
(a Product Management pack, a Business pack, ...) may well want their own
notion of "goal" or "project". Namespacing by pack up front avoids two
packs' categorization conventions colliding in the same, shared
Memory Framework - see docs/08_CAPABILITY_PACKS/CP-01_Personal_Intelligence_Pack/Architecture.md §9.

These are categorization *conventions* layered on the Memory Framework's
existing, unmodified `memory_type: str` field - not a new schema, not a
new table, not a new storage mechanism.
"""

from typing import Any, Mapping

Metadata = Mapping[str, Any]

MEMORY_TYPE_IDENTITY = "personal_identity"
MEMORY_TYPE_GOAL = "personal_goal"
MEMORY_TYPE_PROJECT = "personal_project"
MEMORY_TYPE_REFLECTION = "personal_reflection"
MEMORY_TYPE_PREFERENCE = "personal_preference"
# CP-01.3: insights the Insight Engine derives FROM the five types above -
# namespaced and listed separately (not in ALL_MEMORY_TYPES) so analysis
# code can trivially exclude the engine's own prior output from the raw
# corpus it analyzes, avoiding unbounded self-reinforcement.
MEMORY_TYPE_INSIGHT = "personal_insight"

ALL_MEMORY_TYPES = (
    MEMORY_TYPE_IDENTITY,
    MEMORY_TYPE_GOAL,
    MEMORY_TYPE_PROJECT,
    MEMORY_TYPE_REFLECTION,
    MEMORY_TYPE_PREFERENCE,
)
