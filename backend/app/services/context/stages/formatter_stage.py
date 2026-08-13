from app.services.context.stages.base_stage import PipelineStage
from app.services.context.types import ContextPackage, ContextSection, GroupedItems


class FormatterStage(PipelineStage):
    """Converts grouped items into the final ContextPackage.

    Produces structured output only - ContextSection objects carrying
    plain ContextItems, nothing else. No markdown, no prompt text, no
    LLM-specific formatting of any kind: that's the Prompt Builder's job,
    a separate future subsystem this one has no knowledge of.
    """

    def process(self, data: GroupedItems) -> ContextPackage:
        sections = [
            ContextSection(resource_type=resource_type, items=items)
            for resource_type, items in data.groups.items()
        ]
        item_count = sum(len(section.items) for section in sections)
        return ContextPackage(
            sections=sections,
            estimated_tokens=data.estimated_tokens,
            item_count=item_count,
            truncated=data.truncated,
        )
