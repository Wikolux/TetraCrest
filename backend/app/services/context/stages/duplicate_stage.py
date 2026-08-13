from app.services.context.stages.base_stage import PipelineStage
from app.services.context.types import ContextItem


class DuplicateStage(PipelineStage):
    """Removes exact duplicate items, keyed by (resource_type, resource_id).

    Only exact-key duplicates are removed - no semantic/near-duplicate
    detection, which would require embeddings/similarity that this
    subsystem deliberately never touches. The first occurrence of each key
    wins; input order is otherwise preserved.
    """

    def process(self, data: list[ContextItem]) -> list[ContextItem]:
        seen: set[tuple[str, int]] = set()
        deduplicated: list[ContextItem] = []
        for item in data:
            key = (item.resource_type, item.resource_id)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(item)
        return deduplicated
