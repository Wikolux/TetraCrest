"""DeliveryRequest - what a caller asks the Delivery Specialist to do.
Mirrors DiscoveryRequest's/DecisionRequest's own precedent exactly
(Milestones 3-4).

The operation set maps directly onto this milestone's thirteen named
responsibilities. Two scoping notes, both grounded in already-approved
governance rather than invented here:

- Sprint Planning, Backlog Refinement, Sprint Goal Generation, and
  Capacity Awareness are all **PM-facing framing only** - ARR §9's own
  explicit resolution ("Scrum/Agile delivery cadence awareness ONLY - the
  PM-facing side of sprint/release framing, never engineering-side
  ceremony execution, per PRD §4's explicit Non-Goal"). `capacity` and
  `planned_load`, when used, are always caller-supplied - this specialist
  never invents a team's velocity or capacity figure.
- Backlog Refinement assesses each item's evidence-grounded *readiness/
  clarity*, never re-prioritizes by business value - prioritization is
  the Product Decision Specialist's own responsibility (ARR §3's explicit
  non-responsibility boundary), never recreated here.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class DeliveryOperation(StrEnum):
    PLAN_SPRINT = "plan_sprint"
    REFINE_BACKLOG = "refine_backlog"
    DECOMPOSE_STORY = "decompose_story"
    BREAKDOWN_EPIC = "breakdown_epic"
    GENERATE_ACCEPTANCE_CRITERIA = "generate_acceptance_criteria"
    DETECT_DELIVERY_RISKS = "detect_delivery_risks"
    ANALYZE_DEPENDENCIES = "analyze_dependencies"
    GENERATE_RECOMMENDATION = "generate_recommendation"
    SUPPORT_ENGINEERING_HANDOFF = "support_engineering_handoff"
    SUMMARIZE_DELIVERY = "summarize_delivery"
    SUPPORT_RETROSPECTIVE = "support_retrospective"
    CHECK_LAUNCH_READINESS = "check_launch_readiness"
    RECALL = "recall"


@dataclass(frozen=True)
class DeliveryRequest:
    operation: DeliveryOperation
    text: str = ""
    title: str = ""
    feature_title: str = ""
    items: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    capacity: float | None = None
    planned_load: float | None = None
    stage: str = ""
    product_name: str = ""
    planned: tuple[str, ...] = field(default_factory=tuple)
    actual: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("items", "dependencies", "planned", "actual"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
