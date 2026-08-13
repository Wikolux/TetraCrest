from datetime import datetime, timezone

from app.services.ranking.base_strategy import RankingStrategy
from app.services.ranking.types import RankingCandidate

DEFAULT_SIMILARITY_WEIGHT = 0.7
DEFAULT_RECENCY_WEIGHT = 0.3
DEFAULT_RECENCY_HALF_LIFE_DAYS = 30.0

_SECONDS_PER_DAY = 86400


class DefaultRankingStrategy(RankingStrategy):
    """Weighted blend of semantic similarity and recency only.

    Deliberately excludes frequency, reinforcement, AI-assessed importance,
    and personalization - those need signals this milestone doesn't build
    (access counters, feedback loops, per-user profiles) and are reserved
    for future strategies, so this stays a small, fully-specified baseline.

    similarity_score on a RankingCandidate is whatever VectorStore.search()
    reports - for the current PgVectorStore backend that's a Euclidean
    distance (lower is more similar), not a 0-1 similarity. Converting that
    into a comparable-with-recency 0-1 component is this strategy's job,
    not SemanticSearchService's or VectorStore's - the raw distance those
    layers report is left completely unchanged; only this scoring policy
    interprets it.

    recency is scored as exponential decay by age, controlled by
    recency_half_life_days: a candidate exactly one half-life old scores
    0.5 on the recency component, one two half-lives old scores 0.25, etc.
    """

    def __init__(
        self,
        similarity_weight: float = DEFAULT_SIMILARITY_WEIGHT,
        recency_weight: float = DEFAULT_RECENCY_WEIGHT,
        recency_half_life_days: float = DEFAULT_RECENCY_HALF_LIFE_DAYS,
    ):
        self.similarity_weight = similarity_weight
        self.recency_weight = recency_weight
        self.recency_half_life_days = recency_half_life_days

    def score(self, candidate: RankingCandidate) -> float:
        similarity = self._similarity_component(candidate)
        recency = self._recency_component(candidate)
        return self.similarity_weight * similarity + self.recency_weight * recency

    @staticmethod
    def _similarity_component(candidate: RankingCandidate) -> float:
        distance = max(candidate.similarity_score, 0.0)
        return 1.0 / (1.0 + distance)

    def _recency_component(self, candidate: RankingCandidate) -> float:
        age_days = self._age_in_days(candidate.created_at)
        if age_days <= 0:
            return 1.0
        return 0.5 ** (age_days / self.recency_half_life_days)

    @staticmethod
    def _age_in_days(created_at: datetime) -> float:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
        return age_seconds / _SECONDS_PER_DAY
