from app.services.ranking.base_strategy import RankingStrategy
from app.services.ranking.default_strategy import DefaultRankingStrategy
from app.services.ranking.types import RankedCandidate, RankingCandidate


class RankingEngine:
    """Ranks semantic-search candidates by delegating scoring to a RankingStrategy.

    Purely in-memory: no database access, no knowledge of Memory/
    ConversationMessage models, no coupling to SemanticSearchService or any
    repository. It only knows how to take RankingCandidates, ask the
    configured RankingStrategy for each one's score, and return them sorted
    best-first. Swapping the scoring policy is a different RankingStrategy,
    never a change here.

    Not yet wired into SemanticSearchService - that integration is a
    separate, deliberately small follow-up milestone, kept out of this one
    so the ranking subsystem can be built and tested in isolation first.
    """

    def __init__(self, strategy: RankingStrategy | None = None):
        self.strategy = strategy or DefaultRankingStrategy()

    def rank(self, candidates: list[RankingCandidate]) -> list[RankedCandidate]:
        ranked = [
            RankedCandidate(candidate=candidate, score=self.strategy.score(candidate))
            for candidate in candidates
        ]
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked
