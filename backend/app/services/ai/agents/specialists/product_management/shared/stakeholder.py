"""Stakeholder - a professional role or interest relevant to a product's
decisions or communication (Architecture §7). Structurally distinct from
any CP-01 personal relationship: a Stakeholder record exists only in the
context of a product's decision-making, never as an independent personal
profile of that person (PRD §7.1, §18; Architecture §11).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_STAKEHOLDER


class RaciRole(StrEnum):
    RESPONSIBLE = "responsible"
    ACCOUNTABLE = "accountable"
    CONSULTED = "consulted"
    INFORMED = "informed"


@dataclass(frozen=True)
class Stakeholder:
    name: str
    role_or_interest: str = ""
    raci_role: RaciRole | None = None
    communication_preference: str = ""
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_STAKEHOLDER

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Stakeholder.name is required")

    def to_memory_content(self) -> str:
        parts = [f"Stakeholder: {self.name}."]
        if self.role_or_interest:
            parts.append(f"Role/interest: {self.role_or_interest}.")
        if self.raci_role is not None:
            parts.append(f"RACI: {self.raci_role.value}.")
        if self.communication_preference:
            parts.append(f"Communication preference: {self.communication_preference}.")
        return " ".join(parts)
