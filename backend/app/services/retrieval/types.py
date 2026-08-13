from dataclasses import dataclass
from datetime import datetime


@dataclass
class RetrievalResult:
    """A fully ranked, content-hydrated result ready to hand to
    ContextBuilder.build().

    Structurally satisfies context.types.RankedResult (resource_type,
    resource_id, content, score, created_at, metadata) - something neither
    RankingCandidate nor RankedCandidate can do alone, since neither
    carries `content` (ranking doesn't need it to compute a score; see
    app.services.ranking.types). This is the pipeline's own boundary type,
    produced by adapters.ranking_results_to_context_results, which
    re-attaches content from the original SemanticSearchResult.

    score here is RankingEngine's final blended score, not
    SemanticSearchResult's raw similarity_score.
    """

    resource_type: str
    resource_id: int
    content: str
    score: float
    created_at: datetime
    metadata: dict | None = None
