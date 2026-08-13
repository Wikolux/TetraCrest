from app.services.context.pipeline import ContextPipeline
from app.services.context.stages.budget_stage import BudgetStage
from app.services.context.stages.duplicate_stage import DuplicateStage
from app.services.context.stages.formatter_stage import FormatterStage
from app.services.context.stages.grouping_stage import GroupingStage
from app.services.context.types import ContextItem, ContextPackage, RankedResult


class ContextBuilder:
    """Builds a ContextPackage from already-ranked retrieval results.

    Deterministic, side-effect free, storage-independent, LLM-independent:
    no repository, embedding, semantic-search, ranking, or LLM/prompt code
    is reachable from here. It only ever consumes a list of ranked results
    already handed to it and runs them through ContextPipeline - nothing
    about how those results were retrieved or ranked is this class's
    concern.

    Converts each ranked result into a ContextItem via plain attribute
    access rather than importing app.services.ranking.types.RankedCandidate
    directly: that type currently carries no `content` (ranking doesn't
    need it to compute a score), so it can't fully satisfy ContextItem's
    fields yet. RankedResult (a typing.Protocol in types.py) documents the
    structural shape this builder actually needs; wiring the real ranking
    output into that shape is the integration milestone's job, not this
    one's.
    """

    def __init__(self, pipeline: ContextPipeline | None = None):
        self._pipeline = pipeline

    def build(self, ranked_results: list[RankedResult], max_tokens: int = 4000) -> ContextPackage:
        """Convert ranked_results into a ContextPackage.

        If a pipeline was injected at construction, max_tokens is ignored
        here - the injected pipeline's own BudgetStage (if any) already
        controls its budget. Otherwise a standard
        Duplicate -> Budget -> Grouping -> Formatter pipeline is built
        fresh for this call, parameterized with max_tokens.
        """
        items = [self._to_context_item(result) for result in ranked_results]
        pipeline = self._pipeline or self._default_pipeline(max_tokens)
        return pipeline.run(items)

    @staticmethod
    def _default_pipeline(max_tokens: int) -> ContextPipeline:
        return ContextPipeline(
            [
                DuplicateStage(),
                BudgetStage(max_tokens=max_tokens),
                GroupingStage(),
                FormatterStage(),
            ]
        )

    @staticmethod
    def _to_context_item(result: RankedResult) -> ContextItem:
        return ContextItem(
            resource_type=result.resource_type,
            resource_id=result.resource_id,
            content=result.content,
            score=result.score,
            created_at=result.created_at,
            metadata=result.metadata,
        )
