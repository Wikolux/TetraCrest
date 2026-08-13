from dataclasses import dataclass
from datetime import datetime


@dataclass
class RankingCandidate:
    """A semantic-search result, in the shape the ranking subsystem needs.

    Deliberately its own type rather than reusing SemanticSearchResult -
    the ranking subsystem has no dependency on SemanticSearchService (or
    vice versa) yet. Converting one into the other is deferred to the
    integration milestone that wires RankingEngine into
    SemanticSearchService, so each stays independently testable until then.
    """

    resource_type: str
    resource_id: int
    similarity_score: float
    created_at: datetime
    metadata: dict | None = None


@dataclass
class RankedCandidate:
    """A RankingCandidate plus the final score RankingEngine computed for it.

    Kept separate from RankingCandidate (rather than mutating it in place)
    so a candidate stays an immutable-in-spirit value object and a caller
    can never be confused about whether a score has already been computed.
    """

    candidate: RankingCandidate
    score: float
