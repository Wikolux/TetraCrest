from abc import ABC, abstractmethod

from app.services.ranking.types import RankingCandidate


class RankingStrategy(ABC):
    """Common contract for every ranking policy.

    A concrete strategy turns one RankingCandidate into a single float
    score however its policy requires (similarity+recency today; future
    strategies might blend in frequency, reinforcement, AI-assessed
    importance, or personalization). RankingEngine depends only on this
    interface, so adding a new strategy never means changing the engine.
    """

    @abstractmethod
    def score(self, candidate: RankingCandidate) -> float:
        """Return this candidate's ranking score. Higher must mean better -
        RankingEngine sorts descending by this value."""
        raise NotImplementedError
