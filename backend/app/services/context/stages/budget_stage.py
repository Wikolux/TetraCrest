from app.services.context.stages.base_stage import PipelineStage
from app.services.context.types import BudgetedItems, ContextItem

_CHARS_PER_TOKEN = 4


class BudgetStage(PipelineStage):
    """Keeps the largest ordered prefix of items that fits within max_tokens.

    Estimates each item's token cost as len(content) // 4 - no tokenizer
    dependency, deliberately approximate. Items are kept strictly in their
    incoming order: this stage never reorders or skips an oversized item
    to fit a smaller one further down the list. As soon as one item would
    push the running total over max_tokens, that item and everything
    after it is dropped and truncated is reported True. estimated_tokens
    is the sum for the items actually kept, not the full input.
    """

    def __init__(self, max_tokens: int):
        self.max_tokens = max_tokens

    def process(self, data: list[ContextItem]) -> BudgetedItems:
        kept: list[ContextItem] = []
        total_tokens = 0
        truncated = False

        for item in data:
            item_tokens = self._estimate_tokens(item.content)
            if total_tokens + item_tokens > self.max_tokens:
                truncated = True
                break
            kept.append(item)
            total_tokens += item_tokens

        return BudgetedItems(items=kept, estimated_tokens=total_tokens, truncated=truncated)

    @staticmethod
    def _estimate_tokens(content: str) -> int:
        return len(content) // _CHARS_PER_TOKEN
