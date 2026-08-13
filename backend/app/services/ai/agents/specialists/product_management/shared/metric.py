"""Metric - a quantitative signal the user tracks, including a Product's
North Star Metric where one is defined (Architecture §7).
"""

from dataclasses import dataclass
from datetime import datetime

from app.services.ai.agents.specialists.product_management.shared.types import MEMORY_TYPE_METRIC


@dataclass(frozen=True)
class Metric:
    name: str
    description: str = ""
    target: str = ""
    is_north_star: bool = False
    product_name: str = ""
    created_at: datetime | None = None

    memory_type = MEMORY_TYPE_METRIC

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Metric.name is required")

    def to_memory_content(self) -> str:
        parts = [f"Metric: {self.name}."]
        if self.product_name:
            parts.append(f"Product: {self.product_name}.")
        if self.description:
            parts.append(f"Measures: {self.description}.")
        if self.target:
            parts.append(f"Target: {self.target}.")
        if self.is_north_star:
            parts.append("This is the product's North Star Metric.")
        return " ".join(parts)
