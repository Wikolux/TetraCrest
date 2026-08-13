"""DiscoveryFinding - evidence gathered from users, market, or
competitors, and its current validation status (Architecture §7); the
evidentiary backbone every later recommendation traces to.

`source` is required, not optional: a finding with no stated source is
not evidence, it is an assertion, and Architecture §14's own anti-pattern
("recommending a feature with no supporting Discovery Finding") only has
teeth if a Discovery Finding can never itself be a source-less assertion
in the first place. This is Milestone 1's first instance of the
structural-enforcement discipline ARR §7 requires - the same
construction-time validation pattern CP-01.3's `Insight` type already
proved out, applied here to the entity type Architecture §7 identifies as
the evidence root of the whole pack.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_DISCOVERY_FINDING


class HypothesisStatus(StrEnum):
    UNKNOWN = "unknown"
    VALIDATED = "validated"
    INVALIDATED = "invalidated"


@dataclass(frozen=True)
class DiscoveryFinding:
    summary: str
    source: str
    hypothesis: str = ""
    status: HypothesisStatus = HypothesisStatus.UNKNOWN
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_DISCOVERY_FINDING

    def __post_init__(self) -> None:
        if not self.summary:
            raise ValueError("DiscoveryFinding.summary is required")
        if not self.source:
            raise ValueError(
                "DiscoveryFinding.source is required - a finding must state where its evidence came "
                "from to ever be usable as evidence for something else (ARR §7)"
            )

    def to_memory_content(self) -> str:
        parts = [f"Discovery finding: {self.summary}", f"Source: {self.source}."]
        if self.hypothesis:
            parts.append(f"Hypothesis: {self.hypothesis} (status: {self.status.value}).")
        else:
            parts.append(f"Status: {self.status.value}.")
        return " ".join(parts)
