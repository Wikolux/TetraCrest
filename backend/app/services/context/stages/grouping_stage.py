from app.services.context.stages.base_stage import PipelineStage
from app.services.context.types import BudgetedItems, GroupedItems


class GroupingStage(PipelineStage):
    """Buckets ContextItems by resource_type.

    Groups are ordered by each group's first appearance in the input
    (Python dict insertion order), and each group's items preserve their
    original relative order - no ranking, filtering, or formatting happens
    here, only bucketing. Token accounting is carried forward unchanged
    from BudgetStage.
    """

    def process(self, data: BudgetedItems) -> GroupedItems:
        groups: dict[str, list] = {}
        for item in data.items:
            groups.setdefault(item.resource_type, []).append(item)
        return GroupedItems(groups=groups, estimated_tokens=data.estimated_tokens, truncated=data.truncated)
