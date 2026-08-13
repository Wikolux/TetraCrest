"""Product - something the user is responsible for delivering value
through; the anchor every other CP-02 entity is ultimately traced back to
(Architecture §7, Implementation_Plan.md §6).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_PRODUCT


class ProductLifecycleStage(StrEnum):
    IDEA = "idea"
    DISCOVERY = "discovery"
    BUILDING = "building"
    LAUNCHED = "launched"
    GROWTH = "growth"
    MATURE = "mature"
    SUNSET = "sunset"


@dataclass(frozen=True)
class Product:
    name: str
    customer_segment: str = ""
    value_proposition: str = ""
    lifecycle_stage: ProductLifecycleStage = ProductLifecycleStage.IDEA
    owning_pm: str = ""
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_PRODUCT

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Product.name is required")

    def to_memory_content(self) -> str:
        parts = [f"Product: {self.name}."]
        if self.customer_segment:
            parts.append(f"Customer segment: {self.customer_segment}.")
        if self.value_proposition:
            parts.append(f"Value proposition: {self.value_proposition}.")
        parts.append(f"Lifecycle stage: {self.lifecycle_stage.value}.")
        if self.owning_pm:
            parts.append(f"Owned by: {self.owning_pm}.")
        return " ".join(parts)
