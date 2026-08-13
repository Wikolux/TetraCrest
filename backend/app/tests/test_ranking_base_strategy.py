import pytest

from app.services.ranking.base_strategy import RankingStrategy


def test_ranking_strategy_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        RankingStrategy()


def test_concrete_subclass_implementing_score_can_be_instantiated():
    class _AlwaysZero(RankingStrategy):
        def score(self, candidate):
            return 0.0

    assert isinstance(_AlwaysZero(), RankingStrategy)
