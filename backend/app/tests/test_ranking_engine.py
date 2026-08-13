from datetime import datetime, timezone

from app.services.ranking.base_strategy import RankingStrategy
from app.services.ranking.default_strategy import DefaultRankingStrategy
from app.services.ranking.ranking_engine import RankingEngine
from app.services.ranking.types import RankingCandidate


class _FixedScoreStrategy(RankingStrategy):
    def __init__(self, scores: dict[int, float]):
        self.scores = scores
        self.scored_candidates: list[RankingCandidate] = []

    def score(self, candidate):
        self.scored_candidates.append(candidate)
        return self.scores[candidate.resource_id]


def _candidate(resource_id: int, resource_type: str = "memory") -> RankingCandidate:
    return RankingCandidate(
        resource_type=resource_type,
        resource_id=resource_id,
        similarity_score=0.1,
        created_at=datetime.now(timezone.utc),
    )


def test_rank_delegates_scoring_to_the_strategy():
    strategy = _FixedScoreStrategy({1: 0.5})
    engine = RankingEngine(strategy=strategy)
    candidate = _candidate(1)

    engine.rank([candidate])

    assert strategy.scored_candidates == [candidate]


def test_rank_sorts_candidates_by_score_descending():
    strategy = _FixedScoreStrategy({1: 0.2, 2: 0.9, 3: 0.5})
    engine = RankingEngine(strategy=strategy)
    candidates = [_candidate(1), _candidate(2), _candidate(3)]

    ranked = engine.rank(candidates)

    assert [r.candidate.resource_id for r in ranked] == [2, 3, 1]
    assert [r.score for r in ranked] == [0.9, 0.5, 0.2]


def test_rank_returns_ranked_candidates_pairing_score_with_original_candidate():
    strategy = _FixedScoreStrategy({1: 0.75})
    engine = RankingEngine(strategy=strategy)
    candidate = _candidate(1)

    ranked = engine.rank([candidate])

    assert ranked[0].candidate is candidate
    assert ranked[0].score == 0.75


def test_rank_returns_empty_list_for_empty_input():
    engine = RankingEngine(strategy=_FixedScoreStrategy({}))

    assert engine.rank([]) == []


def test_rank_handles_ties_stably():
    strategy = _FixedScoreStrategy({1: 0.5, 2: 0.5})
    engine = RankingEngine(strategy=strategy)
    candidates = [_candidate(1), _candidate(2)]

    ranked = engine.rank(candidates)

    # Python's sort is stable - equal scores preserve input order
    assert [r.candidate.resource_id for r in ranked] == [1, 2]


def test_rank_handles_mixed_resource_types():
    strategy = _FixedScoreStrategy({1: 0.2, 2: 0.9})
    engine = RankingEngine(strategy=strategy)
    candidates = [_candidate(1, "memory"), _candidate(2, "conversation_message")]

    ranked = engine.rank(candidates)

    assert [r.candidate.resource_type for r in ranked] == ["conversation_message", "memory"]


def test_default_construction_uses_default_ranking_strategy():
    engine = RankingEngine()

    assert isinstance(engine.strategy, DefaultRankingStrategy)


def test_ranking_engine_and_default_strategy_perform_no_database_access():
    # No db/session attribute exists anywhere in this subsystem for either
    # the engine or its default strategy to accidentally use.
    engine = RankingEngine()

    assert not hasattr(engine, "db")
    assert not hasattr(engine.strategy, "db")
