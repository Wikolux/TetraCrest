"""Portfolio - the PM's own set of Products considered together
(Architecture §7); the frame Strategy & Portfolio's cross-product
reasoning operates over once it matures beyond v1 scope (Architecture
§12).

Deliberately has no `memory_type` and no `to_memory_content()`. Per
Architecture §12 and the ARR's own Ownership Matrix (§4), a Portfolio is
not a separately-owned memory category - it shares its owner with Roadmap
State, and portfolio-level reasoning is "a grain extension of Strategy,
not a parallel decision mechanism." Giving Portfolio its own memory
category here would be inventing scope beyond what was approved. This
type exists in Milestone 1 purely as the in-memory composition Architecture
§7 names it as - a structural grouping of Products - not as something
directly persisted in v1/v2.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Portfolio:
    product_names: tuple[str, ...] = field(default_factory=tuple)
    priority_notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.product_names, tuple):
            object.__setattr__(self, "product_names", tuple(self.product_names))
